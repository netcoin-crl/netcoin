#!/bin/sh
# Safe NetCoin public-node uninstall helper. Destructive actions require --yes.
set -eu

PREFIX="${NETCOIN_INSTALL_DIR:-$HOME/.netcoin-public-node}"
SERVICE_NAME="${NETCOIN_SERVICE_NAME:-netcoin-node.service}"
DRY_RUN=0
YES=0
REMOVE_DATA=0

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --service-name) SERVICE_NAME="$2"; shift 2 ;;
    --remove-data) REMOVE_DATA=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes) YES=1; shift ;;
    --help|-h)
      echo "usage: sh tools/uninstall_public_node.sh [--dry-run] [--yes] [--prefix DIR] [--service-name NAME] [--remove-data]"
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

run() {
  echo "+ $*"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@"
  fi
}

cat <<EOF
NetCoin public node uninstall plan
  prefix:       $PREFIX
  service:      $SERVICE_NAME
  remove data:  $REMOVE_DATA
  dry run:      $DRY_RUN
EOF

if [ "$DRY_RUN" -eq 0 ] && [ "$YES" -ne 1 ]; then
  echo "Refusing to uninstall without --yes. Re-run with --dry-run to preview." >&2
  exit 2
fi

if command -v systemctl >/dev/null 2>&1; then
  run systemctl --user stop "$SERVICE_NAME" || true
  run systemctl --user disable "$SERVICE_NAME" || true
fi

if [ -f "$PREFIX/$SERVICE_NAME" ]; then
  run rm -f "$PREFIX/$SERVICE_NAME"
fi
if [ -f "$PREFIX/run-node.sh" ]; then
  run rm -f "$PREFIX/run-node.sh"
fi
if [ -f "$PREFIX/netcoin-node.env" ]; then
  run rm -f "$PREFIX/netcoin-node.env"
fi

if [ "$REMOVE_DATA" -eq 1 ]; then
  run rm -rf "$PREFIX"
else
  echo "Leaving chain data and source tree in $PREFIX. Use --remove-data to delete them."
fi
