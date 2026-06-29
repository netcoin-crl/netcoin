#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/deploy/deploy.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; . "$ENV_FILE"; set +a
fi

AWS_ARGS=()
if [ -n "${AWS_PROFILE:-}" ]; then AWS_ARGS+=(--profile "$AWS_PROFILE"); fi
if [ -n "${AWS_REGION:-}" ]; then AWS_ARGS+=(--region "$AWS_REGION"); fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1" >&2; exit 1; }; }
need aws
need cp
need mktemp

BUILD_ROOT="$(mktemp -d)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

sync_site() {
  local name="$1" source_dir="$2" entry="$3" bucket_var="$4" cf_var="$5"
  local bucket="${!bucket_var:-}"
  local cf="${!cf_var:-}"
  if [ -z "$bucket" ]; then
    echo "==> Skipping $name: $bucket_var is empty"
    return 0
  fi
  local out="$BUILD_ROOT/$name"
  mkdir -p "$out"
  cp -a "$source_dir"/. "$out"/
  if [ -n "$entry" ] && [ -f "$out/$entry" ]; then
    cp "$out/$entry" "$out/index.html"
  fi

  echo "==> Syncing $name -> s3://$bucket/"
  aws "${AWS_ARGS[@]}" s3 sync "$out/" "s3://$bucket/" --delete
  echo "==> Setting no-cache headers on $name HTML files"
  aws "${AWS_ARGS[@]}" s3 cp "$out/" "s3://$bucket/" --recursive --exclude "*" --include "*.html" --cache-control "no-cache, no-store, must-revalidate" --content-type "text/html" >/dev/null

  if [ -n "$cf" ]; then
    echo "==> Invalidating CloudFront $cf for $name"
    aws "${AWS_ARGS[@]}" cloudfront create-invalidation --distribution-id "$cf" --paths "/*" >/dev/null
  fi
}

WALLET_SRC="$ROOT/webwallet-browser/public"
EXPLORER_SRC="$ROOT/webexplorer/public"

sync_site wallet "$WALLET_SRC" wallet.html NETCOIN_WALLET_BUCKET NETCOIN_WALLET_CF
sync_site explorer "$EXPLORER_SRC" index.html NETCOIN_EXPLORER_BUCKET NETCOIN_EXPLORER_CF
sync_site pay "$EXPLORER_SRC" pay.html NETCOIN_PAY_BUCKET NETCOIN_PAY_CF
sync_site merchant "$EXPLORER_SRC" merchant.html NETCOIN_MERCHANT_BUCKET NETCOIN_MERCHANT_CF
sync_site faucet "$EXPLORER_SRC" faucet.html NETCOIN_FAUCET_BUCKET NETCOIN_FAUCET_CF
sync_site status "$EXPLORER_SRC" status.html NETCOIN_STATUS_BUCKET NETCOIN_STATUS_CF
sync_site community "$EXPLORER_SRC" community.html NETCOIN_COMMUNITY_BUCKET NETCOIN_COMMUNITY_CF
sync_site markets "$EXPLORER_SRC" markets.html NETCOIN_MARKETS_BUCKET NETCOIN_MARKETS_CF
sync_site docs "$EXPLORER_SRC" docs.html NETCOIN_DOCS_BUCKET NETCOIN_DOCS_CF
sync_site api "$EXPLORER_SRC" api.html NETCOIN_API_BUCKET NETCOIN_API_CF

echo "==> Static AWS deploy finished"
