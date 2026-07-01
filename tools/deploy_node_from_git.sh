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
# Env: NETCOIN_PREFIX, NETCOIN_SERVICE, NETCOIN_PORT, NETCOIN_GIT_URL.
set -euo pipefail

PREFIX="${NETCOIN_PREFIX:-/opt/netcoin}"
SRC_DIR="$PREFIX/netcoin-v2"                 # the running install (keeps sites/, data, etc.)
GIT_CLONE="$PREFIX/netcoin-git"              # a plain git checkout used as the source of truth
VENV="$SRC_DIR/.venv"
SERVICE="${NETCOIN_SERVICE:-netcoin-node.service}"
PORT="${NETCOIN_PORT:-28444}"
GIT_URL="${NETCOIN_GIT_URL:-git@github.com:netcoin-crl/netcoin.git}"
REF="${1:-main}"

echo "==> Fetching $REF into $GIT_CLONE"
if [ ! -d "$GIT_CLONE/.git" ]; then
  git clone "$GIT_URL" "$GIT_CLONE"
fi
git -C "$GIT_CLONE" fetch --tags --prune origin
git -C "$GIT_CLONE" checkout -q "$REF"
git -C "$GIT_CLONE" pull --ff-only origin "$REF" 2>/dev/null || true
echo "    at $(git -C "$GIT_CLONE" describe --tags --always) ($(git -C "$GIT_CLONE" rev-parse --short HEAD))"

echo "==> Test gate (pytest from the git checkout)"
"$VENV/bin/python" -m pip install -q -e "$GIT_CLONE[test]" 2>/dev/null || "$VENV/bin/python" -m pip install -q pytest
( cd "$GIT_CLONE" && "$VENV/bin/python" -m pytest -q ) || { echo "!! tests failed; aborting deploy"; exit 1; }

echo "==> Backing up current node package"
sudo cp -a "$SRC_DIR/netcoin" "$SRC_DIR/netcoin.bak-$(date +%s)"

echo "==> Syncing node package + pyproject from git (leaves sites/app files untouched)"
sudo rsync -a --delete "$GIT_CLONE/netcoin/" "$SRC_DIR/netcoin/"
sudo cp "$GIT_CLONE/pyproject.toml" "$SRC_DIR/pyproject.toml"
sudo "$VENV/bin/python" -m pip install -q -e "$SRC_DIR"

VER=$("$VENV/bin/python" -c "from netcoin.params import NODE_VERSION; print(NODE_VERSION)")
echo "==> Restarting $SERVICE (node version $VER)"
sudo systemctl restart "$SERVICE"
sleep 3

if curl -fsS "http://127.0.0.1:$PORT/info" >/dev/null; then
  echo "==> Deploy OK — node $VER healthy on :$PORT"
else
  echo "!! health check failed; check: journalctl -u $SERVICE -n 30"
  exit 1
fi
