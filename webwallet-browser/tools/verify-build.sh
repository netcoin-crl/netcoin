#!/usr/bin/env bash
#
# Verify the wallet build is reproducible, and (optionally) that a live
# deployment serves exactly the audited bytes.
#
#   tools/verify-build.sh                      # rebuild and confirm hashes match MANIFEST.txt
#   tools/verify-build.sh https://wallet.netcoin.online   # also check the live site
#
set -euo pipefail
cd "$(dirname "$0")/.."

sri() { printf 'sha384-%s' "$(openssl dgst -sha384 -binary "$1" | openssl base64 -A)"; }

if [ ! -f MANIFEST.txt ]; then echo "no MANIFEST.txt — run tools/build.sh first" >&2; exit 1; fi
WANT_BUNDLE="$(grep 'public/netcoin-wallet.js' MANIFEST.txt | sed -E 's/.*sha384=//')"
WANT_APP="$(grep 'public/wallet-app.js' MANIFEST.txt | sed -E 's/.*sha384=//')"

echo "==> Rebuilding from source"
npm ci --silent && npm run build --silent
GOT_BUNDLE="$(sri public/netcoin-wallet.js)"
GOT_APP="$(sri public/wallet-app.js)"

fail=0
chk() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1"; echo "   manifest: $2"; echo "   rebuilt : $3"; fail=1; fi; }
echo "== reproducibility (rebuild == manifest) =="
chk "netcoin-wallet.js" "$WANT_BUNDLE" "$GOT_BUNDLE"
chk "wallet-app.js"     "$WANT_APP"    "$GOT_APP"

if [ "${1:-}" != "" ]; then
  URL="${1%/}"
  echo "== live deployment ($URL) matches manifest =="
  tmp="$(mktemp -d)"
  curl -fsS "$URL/netcoin-wallet.js" -o "$tmp/b.js"
  curl -fsS "$URL/wallet-app.js"     -o "$tmp/a.js"
  chk "served netcoin-wallet.js" "$WANT_BUNDLE" "$(sri "$tmp/b.js")"
  chk "served wallet-app.js"     "$WANT_APP"    "$(sri "$tmp/a.js")"
  rm -rf "$tmp"
fi

echo ""
[ "$fail" = 0 ] && echo "BUILD VERIFIED ✅" || { echo "VERIFICATION FAILED ❌"; exit 1; }
