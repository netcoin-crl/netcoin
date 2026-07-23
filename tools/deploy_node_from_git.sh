#!/usr/bin/env bash
#
# Git-sourced node deploy (run ON a seed as sudo). Updates only the consensus
# NODE package from a git ref, test-gates it, reinstalls, restarts, and
# health-checks — without touching the site/app files that live alongside it.
#
#   sudo tools/deploy_node_from_git.sh [git-ref]     # default: main
#
# This makes production == git and removes the temptation to edit node code
# directly on the server (which previously hid a crash bug and version skew).
#
# One-time setup on the seed: a read-only clone of the repo at $GIT_CLONE with
# working pull access (deploy key or token for the private repo):
#   git clone git@github.com:netcoin-crl/netcoin.git /opt/netcoin/netcoin-git
#
# Env: NETCOIN_PREFIX, NETCOIN_SERVICE, NETCOIN_PORT, NETCOIN_GIT_URL,
# NETCOIN_DEPLOY_PYTHON, NETCOIN_ENABLE_FAST_CRYPTO.
set -euo pipefail

PREFIX="${NETCOIN_PREFIX:-/opt/netcoin}"
SRC_DIR="$PREFIX/netcoin-v2"                 # the running install (keeps sites/, data, etc.)
GIT_CLONE="$PREFIX/netcoin-git"              # a plain git checkout used as the source of truth
VENV="$SRC_DIR/.venv"
SERVICE="${NETCOIN_SERVICE:-netcoin-node.service}"
PORT="${NETCOIN_PORT:-28444}"
GIT_URL="${NETCOIN_GIT_URL:-git@github.com:netcoin-crl/netcoin.git}"
DEPLOY_PYTHON="${NETCOIN_DEPLOY_PYTHON:-3.13}"
ENABLE_FAST_CRYPTO="${NETCOIN_ENABLE_FAST_CRYPTO:-1}"
REF="${1:-main}"

UV_INSTALLER_VERSION="0.9.16"
UV_INSTALLER_SHA256="81b9594996c7ed9d95bbfb80e7fbdcc4fe1cc9ae83983b4ae86b39c603269207"

ensure_uv() {
  if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
      export PATH="$HOME/.local/bin:$PATH"
    else
      # Pin to a specific installer script version + checksum instead of
      # piping the "latest" installer straight into sh -- that gave a
      # compromised or mistakenly-published astral.sh release unauthenticated
      # root-equivalent code execution on every seed at deploy time.
      echo "==> Installing uv $UV_INSTALLER_VERSION for managed Python $DEPLOY_PYTHON"
      local installer
      installer="$(mktemp)"
      curl -LsSf "https://astral.sh/uv/$UV_INSTALLER_VERSION/install.sh" -o "$installer"
      echo "$UV_INSTALLER_SHA256  $installer" | sha256sum -c - || { echo "!! uv installer checksum mismatch; aborting" >&2; rm -f "$installer"; exit 1; }
      sh "$installer"
      rm -f "$installer"
      export PATH="$HOME/.local/bin:$PATH"
    fi
  fi
}

ensure_venv() {
  ensure_uv
  if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == tuple(map(int, '$DEPLOY_PYTHON'.split('.')[:2])) else 1)" >/dev/null 2>&1; then
    echo "==> Recreating venv with Python $DEPLOY_PYTHON"
    rm -rf "$VENV"
    uv python install "$DEPLOY_PYTHON"
    uv venv --python "$DEPLOY_PYTHON" "$VENV"
  fi
}

install_package() {
  uv pip install --python "$VENV/bin/python" -q -e "$1[test,fast]"
}

configure_fast_crypto() {
  if [ "$ENABLE_FAST_CRYPTO" = "1" ]; then
    echo "==> Enabling NETCOIN_FAST_CRYPTO for $SERVICE"
    sudo mkdir -p "/etc/systemd/system/$SERVICE.d"
    printf "[Service]\nEnvironment=NETCOIN_FAST_CRYPTO=1\n" | sudo tee "/etc/systemd/system/$SERVICE.d/fastcrypto.conf" >/dev/null
  fi
}

echo "==> Fetching $REF into $GIT_CLONE"
if [ ! -d "$GIT_CLONE/.git" ]; then
  git clone "$GIT_URL" "$GIT_CLONE"
fi
git -C "$GIT_CLONE" fetch --tags --prune origin
# Resolve REF to an origin ref if one exists (branch), else assume it's
# already a fetched tag/commit. Then hard-reset onto it rather than
# checkout+pull -- the previous `pull --ff-only ... || true` silently
# swallowed *any* pull failure (auth error, non-ff divergence, network
# blip), so a deploy could silently proceed on stale source with no
# indication the fetch never landed.
if git -C "$GIT_CLONE" show-ref --verify --quiet "refs/remotes/origin/$REF"; then
  git -C "$GIT_CLONE" checkout -q -B "$REF" "origin/$REF"
else
  git -C "$GIT_CLONE" checkout -q "$REF"
fi
echo "    at $(git -C "$GIT_CLONE" describe --tags --always) ($(git -C "$GIT_CLONE" rev-parse --short HEAD))"

echo "==> Test gate (pytest from the git checkout)"
ensure_venv
install_package "$GIT_CLONE"
( cd "$GIT_CLONE" && "$VENV/bin/python" -m pytest -q ) || { echo "!! tests failed; aborting deploy"; exit 1; }

echo "==> Backing up current node package"
BACKUP="$SRC_DIR/netcoin.bak-$(date +%s)"
sudo cp -a "$SRC_DIR/netcoin" "$BACKUP"

rollback() {
  echo "!! rolling back to pre-deploy node package"
  sudo rm -rf "$SRC_DIR/netcoin"
  sudo cp -a "$BACKUP" "$SRC_DIR/netcoin"
  sudo chown -R "$(id -u):$(id -g)" "$SRC_DIR/netcoin"
  install_package "$SRC_DIR" || true
  sudo systemctl daemon-reload || true
  sudo systemctl restart "$SERVICE" || true
}

echo "==> Syncing node package + pyproject from git (leaves sites/app files untouched)"
sudo rsync -a --delete "$GIT_CLONE/netcoin/" "$SRC_DIR/netcoin/"
sudo cp "$GIT_CLONE/pyproject.toml" "$SRC_DIR/pyproject.toml"
sudo chown -R "$(id -u):$(id -g)" "$SRC_DIR"
install_package "$SRC_DIR"
configure_fast_crypto

VER=$("$VENV/bin/python" -c "from netcoin.params import NODE_VERSION; print(NODE_VERSION)")
echo "==> Restarting $SERVICE (node version $VER)"
sudo systemctl daemon-reload || true
sudo systemctl restart "$SERVICE"
sleep 3

if curl -fsS "http://127.0.0.1:$PORT/info" >/dev/null; then
  echo "==> Deploy OK — node $VER healthy on :$PORT"
  sudo rm -rf "$BACKUP"
else
  echo "!! health check failed; check: journalctl -u $SERVICE -n 30"
  rollback
  exit 1
fi
