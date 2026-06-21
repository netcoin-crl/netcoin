#!/usr/bin/env bash
#
# Build a reproducible NetCoin release artifact with checksums and an optional
# signature.
#
# Usage:
#   tools/make_release.sh [REF]
#
#   REF   Git ref to archive (tag, branch, or commit). Defaults to HEAD.
#         For a real release, pass the version tag, e.g. v0.2.0.
#
# Output (in dist/):
#   netcoin-<version>.zip      reproducible source archive from `git archive`
#   SHA256SUMS                 sha256 of the archive
#   SHA256SUMS.asc             detached GPG signature (only if a key is set)
#
# Verify a download with:
#   sha256sum -c SHA256SUMS
#   gpg --verify SHA256SUMS.asc SHA256SUMS   # if signed
#
set -euo pipefail

REF="${1:-HEAD}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# Derive the version from pyproject.toml so the artifact name is canonical.
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
if [ -z "$VERSION" ]; then
  echo "error: could not read version from pyproject.toml" >&2
  exit 1
fi

DIST="$ROOT/dist"
ARCHIVE="netcoin-${VERSION}.zip"
mkdir -p "$DIST"
rm -f "$DIST/$ARCHIVE" "$DIST/SHA256SUMS" "$DIST/SHA256SUMS.asc"

# `git archive` is reproducible: it only includes tracked files at REF and
# honors .gitignore implicitly (untracked junk is never tracked).
echo "Archiving $REF -> dist/$ARCHIVE (version $VERSION)"
git archive --format=zip --prefix="netcoin-${VERSION}/" -o "$DIST/$ARCHIVE" "$REF"

cd "$DIST"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ARCHIVE" > SHA256SUMS
else
  # macOS ships shasum, not sha256sum.
  shasum -a 256 "$ARCHIVE" > SHA256SUMS
fi
echo "Wrote dist/SHA256SUMS:"
cat SHA256SUMS

# Sign if a GPG signing key is available. Set NETCOIN_SIGNING_KEY to a key id,
# or rely on your default GPG key. Skipped silently if gpg is unavailable.
if command -v gpg >/dev/null 2>&1; then
  KEY_ARG=()
  if [ -n "${NETCOIN_SIGNING_KEY:-}" ]; then
    KEY_ARG=(--local-user "$NETCOIN_SIGNING_KEY")
  fi
  if gpg "${KEY_ARG[@]}" --armor --detach-sign --output SHA256SUMS.asc SHA256SUMS 2>/dev/null; then
    echo "Signed dist/SHA256SUMS.asc"
  else
    echo "note: gpg present but signing skipped (no usable key). Set NETCOIN_SIGNING_KEY or import a key to sign." >&2
  fi
else
  echo "note: gpg not found; wrote checksums only. Install gpg to produce SHA256SUMS.asc." >&2
fi

echo "Done. Artifacts in dist/:"
ls -1 "$DIST"
