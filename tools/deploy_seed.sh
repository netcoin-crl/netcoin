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

alert_on_failure() {
  # Opt-in, best-effort deploy-failure notification -- silent no-op unless
  # NETCOIN_DEPLOY_ALERT_WEBHOOK is set (a Slack incoming-webhook or any URL
  # that accepts a JSON {"text": ...} POST). A failed deploy used to just sit
  # there with a down service until someone happened to check.
  local message="$1"
  if [ -n "${NETCOIN_DEPLOY_ALERT_WEBHOOK:-}" ]; then
    curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
      -d "{\"text\":\"NetCoin deploy failure on $(hostname): ${message}\"}" \
      "$NETCOIN_DEPLOY_ALERT_WEBHOOK" >/dev/null 2>&1 || true
  fi
}

configure_fast_crypto() {
  if [ "$ENABLE_FAST_CRYPTO" = "1" ]; then
    echo "==> Enabling NETCOIN_FAST_CRYPTO for $SERVICE"
    mkdir -p "/etc/systemd/system/$SERVICE.d"
    printf "[Service]\nEnvironment=NETCOIN_FAST_CRYPTO=1\n" >"/etc/systemd/system/$SERVICE.d/fastcrypto.conf"
  fi
}

echo "==> Clearing stale deploy artifacts from a previous run"
# Small seeds run /tmp as a size-capped tmpfs (RAM-backed) -- leftover
# mktemp -d staging/backup dirs, old uploaded zips, and stale rollback
# directories from earlier deploys accumulate there indefinitely otherwise.
# A full tmpfs eats into the same RAM budget the test run and node need,
# and was a direct contributor to an out-of-memory kill during a deploy.
find /tmp -maxdepth 1 -mindepth 1 \( -name 'tmp.*' -o -name 'netcoin-*.zip' \) -mmin +120 -exec rm -rf {} + 2>/dev/null || true
find "$PREFIX" -maxdepth 1 -name '*.prev-*' -o -name '*.broken-*' 2>/dev/null | while read -r stale; do rm -rf "$stale" 2>/dev/null || true; done

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
# Move the old tree aside instead of `rm -rf` in place: a recursive delete can
# fail partway (a file busy from a just-killed process, a stale handle after
# an OOM event) and, under `set -e`, that failure used to abort the script
# before the new source was even copied in. Renaming is a single atomic
# operation that can't fail that way; the old tree is deleted best-effort
# afterward and never blocks the deploy either direction.
OLD_SRC="${SRC_DIR}.prev-$(date +%s)"
if [ -d "$SRC_DIR" ]; then
  mv "$SRC_DIR" "$OLD_SRC" 2>/dev/null || rm -rf "$SRC_DIR" || true
fi
cp -a "$NEW" "$SRC_DIR"
rm -rf "$OLD_SRC" 2>/dev/null || true
# Zip archives don't reliably carry correct Unix permission bits (some
# tooling omits them entirely), and cp -a preserves whatever unzip produced.
# Force sane, service-readable permissions regardless of what the archive
# claimed, so a bad zip can't leave the source dir root-only and crash-loop
# the service (which runs as an unprivileged user).
chmod -R a+rX "$SRC_DIR"

install_venv
configure_fast_crypto

# Preflight: the full suite plus its own subprocess churn needs real headroom.
# A box with no swap and little free memory will get the pytest run itself
# OOM-killed outright (seen for real: a ~900MB instance with 0 swap died mid
# run). Warn loudly, and add swap automatically rather than silently letting
# the deploy crash-loop the same way again.
MIN_AVAILABLE_KB="${NETCOIN_DEPLOY_MIN_MEM_KB:-1048576}"  # 1GB, override via env
available_kb="$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
swap_total_kb="$(awk '/SwapTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
if [ "$available_kb" -lt "$MIN_AVAILABLE_KB" ] && [ "$swap_total_kb" -eq 0 ]; then
  echo "==> Low memory ($((available_kb / 1024))MB available, no swap) -- adding a 2GB swapfile so the test run doesn't get OOM-killed"
  if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile
  fi
  swapon /swapfile 2>/dev/null || true
  grep -q '^/swapfile ' /etc/fstab 2>/dev/null || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

echo "==> Running tests"
if ! ( cd "$SRC_DIR" && "$VENV/bin/python" -m pytest -q ); then
  echo "!! tests failed; rolling back source"
  # Same move-aside-first approach as above: a failed `rm -rf` here used to
  # abort the whole rollback under `set -e`, leaving the service down with no
  # working source at all and no restart attempted -- exactly the failure
  # mode that took seed3 offline. Every step below is best-effort so the
  # restore and restart always happen regardless of what the cleanup does.
  BROKEN_SRC="${SRC_DIR}.broken-$(date +%s)"
  mv "$SRC_DIR" "$BROKEN_SRC" 2>/dev/null || rm -rf "$SRC_DIR" || true
  cp -a "$PREV/netcoin-v2" "$SRC_DIR"
  chmod -R a+rX "$SRC_DIR"
  rm -rf "$BROKEN_SRC" 2>/dev/null || true
  systemctl daemon-reload || true
  systemctl start "$SERVICE" || true
  alert_on_failure "test suite failed deploying to $SRC_DIR; rolled back and restarted $SERVICE"
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
  # Seeds that also host nginx serve static sites from $PREFIX/sites, a
  # directory separate from $SRC_DIR that nothing above this point touches.
  # Skipping this step is exactly the bug that let a deployed nav/UI change
  # pass its healthcheck while nginx kept serving the previous version.
  SITES_DOCROOT="$PREFIX/sites"
  if [ -d "$SITES_DOCROOT" ] && [ -d "$SRC_DIR/sites" ]; then
    echo "==> Syncing static sites to $SITES_DOCROOT"
    rsync -a --delete "$SRC_DIR/sites/" "$SITES_DOCROOT/"
    chmod -R a+rX "$SITES_DOCROOT"
  fi
  echo "==> Deploy OK"
  rm -rf "$PREV" "$STAGE"
else
  echo "!! health check failed; rolling back source and restarting"
  systemctl stop "$SERVICE" || true
  # Same move-aside-first rollback as the test-failure path above -- a failed
  # `rm -rf` here must never block the restore or restart.
  BROKEN_SRC="${SRC_DIR}.broken-$(date +%s)"
  mv "$SRC_DIR" "$BROKEN_SRC" 2>/dev/null || rm -rf "$SRC_DIR" || true
  cp -a "$PREV/netcoin-v2" "$SRC_DIR"
  chmod -R a+rX "$SRC_DIR"
  rm -rf "$BROKEN_SRC" 2>/dev/null || true
  systemctl daemon-reload || true
  systemctl start "$SERVICE" || true
  alert_on_failure "health check failed after deploying to $SRC_DIR; rolled back and restarted $SERVICE"
  exit 1
fi
