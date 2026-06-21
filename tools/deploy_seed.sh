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
# Env overrides: NETCOIN_PREFIX, NETCOIN_SERVICE, NETCOIN_PORT, NETCOIN_DATA_DIR.
set -euo pipefail

PREFIX="${NETCOIN_PREFIX:-/opt/netcoin}"
SRC_DIR="$PREFIX/netcoin-v2"
VENV="$SRC_DIR/.venv"
SERVICE="${NETCOIN_SERVICE:-netcoin-node.service}"
PORT="${NETCOIN_PORT:-28444}"
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

echo "==> Reinstalling venv"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -e "$SRC_DIR"

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
sleep 2

echo "==> Health check http://127.0.0.1:$PORT/info"
if curl -fsS "http://127.0.0.1:$PORT/info" >/dev/null; then
  echo "==> Deploy OK"
  rm -rf "$PREV" "$STAGE"
else
  echo "!! health check failed; rolling back source and restarting"
  systemctl stop "$SERVICE" || true
  rm -rf "$SRC_DIR"; cp -a "$PREV/netcoin-v2" "$SRC_DIR"
  systemctl start "$SERVICE" || true
  exit 1
fi
