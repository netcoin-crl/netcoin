#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/deploy/deploy.env}"

echo "==> Step 1/3: AWS static sites"
"$ROOT/deploy/deploy_static_aws.sh" "$ENV_FILE"

echo "==> Step 2/3: node rollout"
"$ROOT/deploy/deploy_all_nodes.sh" "$ENV_FILE"

echo "==> Step 3/3: GitHub push"
"$ROOT/deploy/push_github.sh" "$ENV_FILE"

echo "==> Full deploy flow finished"
