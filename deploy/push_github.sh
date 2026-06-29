#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/deploy/deploy.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; . "$ENV_FILE"; set +a
fi

REMOTE="${NETCOIN_GITHUB_REMOTE:-}"
BRANCH="${NETCOIN_GITHUB_BRANCH:-v1-wallet-modes-site-split}"
BASE="${NETCOIN_GITHUB_BASE:-main}"
MESSAGE="${NETCOIN_GITHUB_MESSAGE:-Deploy wallet modes and site split}"

cd "$ROOT"
if [ -z "$REMOTE" ]; then
  if git remote get-url origin >/dev/null 2>&1; then
    REMOTE="$(git remote get-url origin)"
  else
    echo "NETCOIN_GITHUB_REMOTE is required, or configure git remote origin" >&2
    exit 2
  fi
fi

if [ ! -d .git ]; then
  git init
  git remote add origin "$REMOTE"
else
  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$REMOTE"
  else
    git remote add origin "$REMOTE"
  fi
fi

git fetch origin "$BASE" || true
if git show-ref --verify --quiet "refs/remotes/origin/$BASE"; then
  git checkout -B "$BRANCH" "origin/$BASE"
else
  git checkout -B "$BRANCH"
fi

git add -A
if git diff --cached --quiet; then
  echo "==> No changes to commit"
else
  git commit -m "$MESSAGE"
fi

git push -u origin "$BRANCH"

echo "==> GitHub branch pushed: $BRANCH"
if command -v gh >/dev/null 2>&1; then
  gh pr create --base "$BASE" --head "$BRANCH" --title "$MESSAGE" --body "Wallet modes, tab layout, site split, and deployment prep." || true
else
  echo "Install GitHub CLI or open a PR manually from $BRANCH into $BASE."
fi
