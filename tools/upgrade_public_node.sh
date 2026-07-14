#!/bin/sh
# NetCoin public-node upgrade helper. Preserves data and updates the installed source checkout.
set -eu

PREFIX="${NETCOIN_INSTALL_DIR:-$HOME/.netcoin-public-node}"
SERVICE_NAME="${NETCOIN_SERVICE_NAME:-netcoin-node.service}"
TARGET_REF="${NETCOIN_UPGRADE_REF:-main}"
DRY_RUN=0
RESTART=0

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --service-name) SERVICE_NAME="$2"; shift 2 ;;
    --ref) TARGET_REF="$2"; shift 2 ;;
    --restart) RESTART=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h)
      echo "usage: sh tools/upgrade_public_node.sh [--dry-run] [--restart] [--prefix DIR] [--service-name NAME] [--ref REF]"
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

SRC="$PREFIX/src"
VENV="$PREFIX/.venv"

run() {
  echo "+ $*"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@"
  fi
}

cat <<EOF
NetCoin public node upgrade plan
  prefix:   $PREFIX
  source:   $SRC
  ref:      $TARGET_REF
  service:  $SERVICE_NAME
  restart:  $RESTART
  dry run:  $DRY_RUN
EOF

if [ "$DRY_RUN" -eq 0 ] && [ ! -d "$SRC/.git" ]; then
  echo "missing installed git checkout at $SRC; run install_public_node.sh first" >&2
  exit 2
fi

run git -C "$SRC" fetch --tags --prune
run git -C "$SRC" checkout "$TARGET_REF"
run git -C "$SRC" pull --ff-only
run "$VENV/bin/python" -m pip install -U pip
run "$VENV/bin/python" -m pip install -e "$SRC"
run "$VENV/bin/python" -m compileall -q "$SRC/netcoin" "$SRC/tools"

if [ "$RESTART" -eq 1 ]; then
  if command -v systemctl >/dev/null 2>&1; then
    run systemctl --user restart "$SERVICE_NAME"
  else
    echo "systemctl not found; restart $PREFIX/run-node.sh manually"
  fi
fi
