#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/deploy/deploy.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; . "$ENV_FILE"; set +a
fi

NODES_FILE="${NETCOIN_NODES_FILE:-$ROOT/deploy/nodes.txt}"
RELEASE_ZIP="${NETCOIN_RELEASE_ZIP:-}"
REMOTE_RELEASE="${NETCOIN_REMOTE_RELEASE:-/tmp/netcoin-release.zip}"
REMOTE_DEPLOY="${NETCOIN_REMOTE_DEPLOY:-/tmp/netcoin-deploy-seed.sh}"
SSH_USER="${NETCOIN_SSH_USER:-ubuntu}"
SSH_KEY="${NETCOIN_SSH_KEY:-}"
SERVICE="${NETCOIN_DEPLOY_SERVICE:-netcoin-node.service}"
PORT="${NETCOIN_DEPLOY_PORT:-28444}"
CONTINUE_ON_ERROR="${NETCOIN_CONTINUE_ON_ERROR:-0}"

if [ -z "$RELEASE_ZIP" ]; then echo "NETCOIN_RELEASE_ZIP is required" >&2; exit 2; fi
case "$RELEASE_ZIP" in /*) ;; *) RELEASE_ZIP="$ROOT/$RELEASE_ZIP" ;; esac
if [ ! -f "$RELEASE_ZIP" ]; then echo "release zip not found: $RELEASE_ZIP" >&2; exit 2; fi
if [ ! -f "$NODES_FILE" ]; then echo "nodes file not found: $NODES_FILE" >&2; exit 2; fi

SSH_OPTS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [ -n "$SSH_KEY" ]; then SSH_OPTS+=(-i "$SSH_KEY"); fi

remote_for_line() {
  local line="$1"
  if [[ "$line" == *@* ]]; then printf '%s' "$line"; else printf '%s@%s' "$SSH_USER" "$line"; fi
}

failures=0
while IFS= read -r raw || [ -n "$raw" ]; do
  line="${raw%%#*}"
  line="$(printf '%s' "$line" | xargs)"
  [ -z "$line" ] && continue
  host="$(remote_for_line "$line")"
  echo "==> Deploying node $host"
  if scp "${SSH_OPTS[@]}" "$RELEASE_ZIP" "$ROOT/tools/deploy_seed.sh" "$host:/tmp/" && \
     ssh "${SSH_OPTS[@]}" "$host" "sudo NETCOIN_SERVICE='$SERVICE' NETCOIN_PORT='$PORT' bash '$REMOTE_DEPLOY' --zip '$REMOTE_RELEASE'"; then
    echo "==> Node deploy OK: $host"
  else
    echo "!! Node deploy failed: $host" >&2
    failures=$((failures + 1))
    if [ "$CONTINUE_ON_ERROR" != "1" ]; then exit 1; fi
  fi
done < "$NODES_FILE"

if [ "$failures" -gt 0 ]; then
  echo "!! Finished with $failures failed node(s)" >&2
  exit 1
fi

echo "==> All node deploys finished"
