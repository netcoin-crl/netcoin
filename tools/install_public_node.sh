#!/bin/sh
# NetCoin M3 public testnet node installer.
# Review this script before running. It does not start systemd unless --write-systemd is supplied.
set -eu

PREFIX="$HOME/.netcoin-public-node"
ADVERTISE=""
BANDWIDTH_MODE="home"
WRITE_SYSTEMD=0
DRY_RUN=0
REPO_URL="https://github.com/netcoin-crl/netcoin.git"

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --advertise) ADVERTISE="$2"; shift 2 ;;
    --bandwidth-mode) BANDWIDTH_MODE="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --write-systemd) WRITE_SYSTEMD=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h)
      echo "usage: sh tools/install_public_node.sh [--dry-run] [--prefix DIR] [--advertise HOST:28444] [--bandwidth-mode home|normal|low] [--write-systemd]"
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$ADVERTISE" ]; then
  ADVERTISE="YOUR_PUBLIC_IP_OR_DNS:28444"
fi

cat <<EOF
NetCoin public node install plan
  prefix:          $PREFIX
  advertise:       $ADVERTISE
  bandwidth mode:  $BANDWIDTH_MODE
  repo:            $REPO_URL
  write systemd:   $WRITE_SYSTEMD
  dry run:         $DRY_RUN
EOF

run() {
  echo "+ $*"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@"
  fi
}

run mkdir -p "$PREFIX"
if [ ! -d "$PREFIX/src/.git" ]; then
  run git clone "$REPO_URL" "$PREFIX/src"
else
  echo "+ git -C $PREFIX/src pull --ff-only"
  if [ "$DRY_RUN" -eq 0 ]; then git -C "$PREFIX/src" pull --ff-only; fi
fi
run python3 -m venv "$PREFIX/.venv"
if [ "$DRY_RUN" -eq 0 ]; then
  "$PREFIX/.venv/bin/python" -m pip install -U pip
  "$PREFIX/.venv/bin/python" -m pip install -e "$PREFIX/src"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "+ would write $PREFIX/netcoin-node.env"
else
  cat > "$PREFIX/netcoin-node.env" <<EOF
NETCOIN_DATA_DIR=$PREFIX/data
NETCOIN_ADVERTISE=$ADVERTISE
NETCOIN_BANDWIDTH_MODE=$BANDWIDTH_MODE
NETCOIN_P2P_PORT=28444
EOF
  echo "+ wrote $PREFIX/netcoin-node.env"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "+ would write $PREFIX/run-node.sh"
else
  cat > "$PREFIX/run-node.sh" <<EOF
#!/bin/sh
set -eu
. "$PREFIX/netcoin-node.env"
exec "$PREFIX/.venv/bin/python" -m netcoin --data "\$NETCOIN_DATA_DIR" node --host 0.0.0.0 --port "\$NETCOIN_P2P_PORT" --advertise "\$NETCOIN_ADVERTISE"
EOF
  chmod +x "$PREFIX/run-node.sh"
  echo "+ wrote $PREFIX/run-node.sh"
fi

if [ "$WRITE_SYSTEMD" -eq 1 ]; then
  SERVICE="$PREFIX/netcoin-node.service"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ would write $SERVICE"
  else
    cat > "$SERVICE" <<EOF
[Unit]
Description=NetCoin public testnet node
After=network-online.target

[Service]
Type=simple
EnvironmentFile=$PREFIX/netcoin-node.env
ExecStart=$PREFIX/run-node.sh
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    echo "+ wrote $SERVICE"
  fi
  echo "Review, then install manually: sudo cp $SERVICE /etc/systemd/system/netcoin-node.service"
fi

echo "Next: open/forward TCP 28444, run $PREFIX/run-node.sh, then submit endpoint evidence."
