#!/usr/bin/env bash
#
# Safely install or update NetCoin on a seed node (run ON the seed, as root/sudo).
#
# It backs up first, updates the source from a provided directory or a release
# zip, reinstalls the venv, runs the test suite, restarts the node service, and
# health-checks /info. If the health check fails it restarts the service from the
# pre-update source it backed up, so a bad deploy does not leave the node down.
#
# Usage:
#   tools/deploy_seed.sh --source /path/to/new/netcoin-v2
#   tools/deploy_seed.sh --zip /path/to/netcoin-v2-public-testnet-ready.zip
#
# Env overrides: NETCOIN_PREFIX, NETCOIN_SERVICE, NETCOIN_PORT, NETCOIN_DATA_DIR,
# NETCOIN_DEPLOY_PYTHON, NETCOIN_ENABLE_FAST_CRYPTO.
set -euo pipefail

PREFIX="${NETCOIN_PREFIX:-/opt/netcoin}"
SRC_DIR="$PREFIX/netcoin-v2"
VENV="$SRC_DIR/.venv"
SERVICE="${NETCOIN_SERVICE:-netcoin-node.service}"
PORT="${NETCOIN_PORT:-28444}"
DEPLOY_PYTHON="${NETCOIN_DEPLOY_PYTHON:-3.13}"
ENABLE_FAST_CRYPTO="${NETCOIN_ENABLE_FAST_CRYPTO:-1}"
UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$PREFIX/uv-python}"
SOURCE=""
ZIP=""

while [ $# -gt 0 ]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --zip) ZIP="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$SOURCE" ] && [ -z "$ZIP" ]; then
  echo "error: provide --source <dir> or --zip <file>" >&2
  exit 2
fi

ensure_uv() {
  if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
      export PATH="$HOME/.local/bin:$PATH"
    else
      echo "==> Installing uv for managed Python $DEPLOY_PYTHON"
      curl -LsSf https://astral.sh/uv/install.sh | sh
      export PATH="$HOME/.local/bin:$PATH"
    fi
  fi
}

install_venv() {
  echo "==> Reinstalling venv with Python $DEPLOY_PYTHON"
  ensure_uv
  mkdir -p "$UV_PYTHON_INSTALL_DIR"
  export UV_PYTHON_INSTALL_DIR
  rm -rf "$VENV"
  uv python install "$DEPLOY_PYTHON"
  uv venv --python "$DEPLOY_PYTHON" "$VENV"
  uv pip install --python "$VENV/bin/python" -q -e "$SRC_DIR[test,fast]"
  chmod -R a+rX "$UV_PYTHON_INSTALL_DIR" "$VENV"
}

configure_fast_crypto() {
  if [ "$ENABLE_FAST_CRYPTO" = "1" ]; then
    echo "==> Enabling NETCOIN_FAST_CRYPTO for $SERVICE"
    mkdir -p "/etc/systemd/system/$SERVICE.d"
    printf "[Service]\nEnvironment=NETCOIN_FAST_CRYPTO=1\n" >"/etc/systemd/system/$SERVICE.d/fastcrypto.conf"
  fi
}

echo "==> Backing up before deploy"
if [ -x "$SRC_DIR/tools/backup_node.sh" ]; then
  "$SRC_DIR/tools/backup_node.sh" || echo "warning: backup script failed; continuing"
fi

PREV="$(mktemp -d)"
if [ -d "$SRC_DIR" ]; then
  echo "==> Saving current source for rollback -> $PREV"
  cp -a "$SRC_DIR" "$PREV/netcoin-v2"
fi

echo "==> Stopping $SERVICE"
systemctl stop "$SERVICE" || true

echo "==> Updating source"
STAGE="$(mktemp -d)"
if [ -n "$ZIP" ]; then
  unzip -q "$ZIP" -d "$STAGE"
  NEW="$(find "$STAGE" -maxdepth 2 -type d -name netcoin -printf '%h\n' | head -1)"
  NEW="${NEW:-$STAGE/netcoin-v2}"
else
  NEW="$SOURCE"
fi
rm -rf "$SRC_DIR"
cp -a "$NEW" "$SRC_DIR"
# Zip archives don't reliably carry correct Unix permission bits (some
# tooling omits them entirely), and cp -a preserves whatever unzip produced.
# Force sane, service-readable permissions regardless of what the archive
# claimed, so a bad zip can't leave the source dir root-only and crash-loop
# the service (which runs as an unprivileged user).
chmod -R a+rX "$SRC_DIR"

install_venv
configure_fast_crypto

echo "==> Running tests"
if ! ( cd "$SRC_DIR" && "$VENV/bin/python" -m pytest -q ); then
  echo "!! tests failed; rolling back source"
  rm -rf "$SRC_DIR"; cp -a "$PREV/netcoin-v2" "$SRC_DIR"
  systemctl start "$SERVICE" || true
  exit 1
fi

echo "==> Restarting $SERVICE"
systemctl daemon-reload || true
systemctl start "$SERVICE"

# The node replays the whole chain before serving HTTP. On a small,
# memory-pressured seed (1-2 GB, also hosting nginx + the sites) that cold
# replay of a long chain can take several minutes, so the window is generous
# (600s) — a deploy that rolls back only because the box was slow to replay is
# a false negative that causes a needless outage. Override with
# NETCOIN_HEALTHCHECK_TRIES if a box needs even longer.
HEALTHCHECK_TRIES="${NETCOIN_HEALTHCHECK_TRIES:-300}"
echo "==> Health check http://127.0.0.1:$PORT/info (up to $((HEALTHCHECK_TRIES * 2))s)"
HEALTHY=""
for _ in $(seq 1 "$HEALTHCHECK_TRIES"); do
  sleep 2
  if curl -fsS "http://127.0.0.1:$PORT/info" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
done
if [ -n "$HEALTHY" ]; then
  echo "==> Deploy OK"
  rm -rf "$PREV" "$STAGE"
else
  echo "!! health check failed; rolling back source and restarting"
  systemctl stop "$SERVICE" || true
  rm -rf "$SRC_DIR"; cp -a "$PREV/netcoin-v2" "$SRC_DIR"
  systemctl start "$SERVICE" || true
  exit 1
fi
