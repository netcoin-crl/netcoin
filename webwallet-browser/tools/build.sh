#!/usr/bin/env bash
#
# Reproducible wallet build. Produces a byte-deterministic bundle, pins the
# Subresource-Integrity hashes into wallet.html, and writes (optionally signs) a
# manifest so anyone can verify the served wallet matches this source commit.
#
#   tools/build.sh
#
# Determinism comes from: a pinned lockfile (`npm ci`) + a pinned esbuild
# version. Re-running yields identical hashes (verified by tools/verify-build.sh).
#
# Env: NETCOIN_SIGNING_KEY (optional gpg key id) to sign the manifest.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "==> Installing pinned deps (npm ci)"
npm ci --silent

echo "==> Building bundle (esbuild)"
npm run build --silent

sri() { printf 'sha384-%s' "$(openssl dgst -sha384 -binary "$1" | openssl base64 -A)"; }
sha256() { openssl dgst -sha256 -binary "$1" | openssl base64 -A; }

BUNDLE="public/netcoin-wallet.js"
APP="public/wallet-app.js"
HTML="public/wallet.html"

BUNDLE_SRI="$(sri "$BUNDLE")"
APP_SRI="$(sri "$APP")"

echo "==> Pinning SRI into $HTML"
# Replace the integrity="..." on each known script src so the page always
# matches the freshly built assets.
perl -0pi -e "s#(src=\"netcoin-wallet\.js\" integrity=\")[^\"]*#\${1}${BUNDLE_SRI}#" "$HTML"
perl -0pi -e "s#(src=\"wallet-app\.js\" integrity=\")[^\"]*#\${1}${APP_SRI}#" "$HTML"

COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
MANIFEST="MANIFEST.txt"
{
  echo "NetCoin wallet build manifest"
  echo "source_commit: ${COMMIT}"
  echo "built_from: webwallet-browser/ (npm ci + npm run build)"
  echo ""
  printf "%-26s sha384=%s\n" "$BUNDLE" "$BUNDLE_SRI"
  printf "%-26s sha384=%s\n" "$APP" "$APP_SRI"
  echo ""
  echo "sha256 (base64):"
  printf "  %-24s %s\n" "$(basename "$BUNDLE")" "$(sha256 "$BUNDLE")"
  printf "  %-24s %s\n" "$(basename "$APP")" "$(sha256 "$APP")"
  printf "  %-24s %s\n" "wallet.html" "$(sha256 "$HTML")"
} > "$MANIFEST"

echo "==> Wrote $MANIFEST"
cat "$MANIFEST"

# Optional signature (mirrors tools/make_release.sh in the node repo).
if [ -n "${NETCOIN_SIGNING_KEY:-}" ] && command -v gpg >/dev/null 2>&1; then
  if gpg --batch --yes --local-user "$NETCOIN_SIGNING_KEY" --armor --detach-sign --output "${MANIFEST}.asc" "$MANIFEST" 2>/dev/null; then
    echo "==> Signed ${MANIFEST}.asc"
  else
    echo "note: gpg signing skipped (NETCOIN_SIGNING_KEY is not usable)." >&2
  fi
else
  echo "note: set NETCOIN_SIGNING_KEY to sign ${MANIFEST}.asc." >&2
fi
