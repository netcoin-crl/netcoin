#!/usr/bin/env bash
#
# Back up a NetCoin seed node into a single timestamped archive.
#
# Captures (when present): chain/wallet data dir, faucet wallet + state, peer
# file, systemd unit files, explorer output, monitor config, and the release zip.
# Wallet files ARE included, so store the resulting archive somewhere private and
# encrypted. Run as a user that can read the paths (root/sudo on a seed).
#
# Usage:
#   tools/backup_node.sh [OUTPUT_DIR]
#
# Override any path with the matching env var (see defaults below).
set -euo pipefail

OUTPUT_DIR="${1:-${NETCOIN_BACKUP_DIR:-/opt/netcoin/backups}}"
DATA_DIR="${NETCOIN_DATA_DIR:-/opt/netcoin/.netcoin-testnet}"
WALLETS_DIR="${NETCOIN_WALLETS_DIR:-/opt/netcoin/wallets}"
FAUCET_DIR="${NETCOIN_FAUCET_DIR:-/opt/netcoin/faucet}"
EXPLORER_DIR="${NETCOIN_EXPLORER_DIR:-/var/www/netcoin-explorer}"
MONITOR_DIR="${NETCOIN_MONITOR_DIR:-/opt/netcoin/monitor}"
RELEASE_ZIP="${NETCOIN_RELEASE_ZIP:-/opt/netcoin/netcoin-v2-public-testnet-ready.zip}"
SYSTEMD_UNITS=("/etc/systemd/system/netcoin-node.service" "/etc/systemd/system/netcoin-faucet.service")

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STAGE="$(mktemp -d)"
DEST="$STAGE/netcoin-backup-$STAMP"
mkdir -p "$DEST"

copy_if_present() {
  local src="$1" name="$2"
  if [ -e "$src" ]; then
    mkdir -p "$DEST/$name"
    cp -a "$src" "$DEST/$name/" 2>/dev/null || true
    echo "  + $name <- $src"
  else
    echo "  - $name (skipped; $src not found)"
  fi
}

echo "Backing up NetCoin node -> $OUTPUT_DIR/netcoin-backup-$STAMP.tar.gz"
copy_if_present "$DATA_DIR" "data"
copy_if_present "$WALLETS_DIR" "wallets"
copy_if_present "$FAUCET_DIR" "faucet"
copy_if_present "$EXPLORER_DIR" "explorer"
copy_if_present "$MONITOR_DIR" "monitor"
copy_if_present "$RELEASE_ZIP" "release"
for unit in "${SYSTEMD_UNITS[@]}"; do
  copy_if_present "$unit" "systemd"
done

# A small manifest for restore-time sanity.
{
  echo "created_utc=$STAMP"
  echo "host=$(hostname)"
  echo "data_dir=$DATA_DIR"
} > "$DEST/MANIFEST.txt"

mkdir -p "$OUTPUT_DIR"
ARCHIVE="$OUTPUT_DIR/netcoin-backup-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$STAGE" "netcoin-backup-$STAMP"
chmod 600 "$ARCHIVE"
rm -rf "$STAGE"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ARCHIVE"
else
  shasum -a 256 "$ARCHIVE"
fi
echo "Done. Keep this archive private (it contains wallet files)."
