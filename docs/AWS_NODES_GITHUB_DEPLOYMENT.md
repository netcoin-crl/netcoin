# AWS, node, and GitHub deployment plan

This project now includes deployment helper scripts under `deploy/`.
They are designed to be run from the repository root on an operator machine that already has AWS, SSH, and GitHub credentials configured.

## Order

The requested deployment order is:

1. Push static sites to AWS.
2. Roll out the node release to seed/node hosts.
3. Push the code branch to GitHub.

The all-in-one runner is:

```bash
cp deploy/deploy.env.example deploy/deploy.env
# edit deploy/deploy.env and deploy/nodes.txt first
./deploy/run_full_deploy.sh deploy/deploy.env
```

## AWS static sites

The script `deploy/deploy_static_aws.sh` syncs static files to S3 buckets and optionally invalidates CloudFront distributions.

It maps:

- `wallet.netcoin.online` -> `webwallet-browser/public`, with `wallet.html` copied to `index.html`
- `explorer.netcoin.online` -> `webexplorer/public/index.html`
- `pay.netcoin.online` -> `webexplorer/public/pay.html`
- `merchant.netcoin.online` -> `webexplorer/public/merchant.html`
- `faucet.netcoin.online` -> `webexplorer/public/faucet.html`
- `status.netcoin.online` -> `webexplorer/public/status.html`
- `community.netcoin.online` -> `webexplorer/public/community.html`
- `markets.netcoin.online` -> `webexplorer/public/markets.html`
- `docs.netcoin.online` -> `webexplorer/public/docs.html`
- `api.netcoin.online` -> `webexplorer/public/api.html`

Run only static deploy:

```bash
./deploy/deploy_static_aws.sh deploy/deploy.env
```

## Node rollout

Create `deploy/nodes.txt` from `deploy/nodes.example.txt`.

Each line can be:

```text
ubuntu@seed1.netcoin.online
seed2.netcoin.online
203.0.113.10
```

If a line does not include `user@`, the script uses `NETCOIN_SSH_USER` from `deploy.env`.

Run node rollout only:

```bash
./deploy/deploy_all_nodes.sh deploy/deploy.env
```

The script copies the release zip and `tools/deploy_seed.sh` to each host, then runs the remote deploy script with sudo. The existing `tools/deploy_seed.sh` backs up first, installs the new source, runs tests, restarts the node service, health-checks `/info`, and rolls back if the health check fails.

## GitHub push

Set this in `deploy/deploy.env`:

```bash
NETCOIN_GITHUB_REMOTE=https://github.com/Adoniyas1/YOUR_REPO.git
NETCOIN_GITHUB_BRANCH=v1-wallet-modes-site-split
NETCOIN_GITHUB_BASE=main
```

Then run:

```bash
./deploy/push_github.sh deploy/deploy.env
```

The script initializes git if needed, creates or resets the deployment branch, commits all files, pushes to GitHub, and opens a PR when the GitHub CLI is installed.

## Required operator credentials

Before running these scripts on your machine, confirm:

- `aws sts get-caller-identity` works.
- Your AWS IAM user/role can write the S3 buckets and create CloudFront invalidations.
- SSH works for every node in `deploy/nodes.txt`.
- The remote user can run `sudo` for the deploy script.
- Git can push to the target GitHub repo.
- The target GitHub repo exists and the GitHub App/CLI/user has access.

## Safety checks before running

Run locally first:

```bash
node --check webwallet-browser/public/wallet-app.js
node --check webexplorer/public/explorer-app.js
node --check webexplorer/public/admin-app.js
python -m py_compile netcoin/apps.py netcoin/node.py netcoin/explorer_server.py tools/verify_release.py
PYTHONPATH=. pytest -q tests/test_browser_upgrade_assets.py tests/test_wallet_features.py tests/test_deployment_qa.py
```

Then run the deployment QA tool:

```bash
python tools/deployment_qa.py --data-dir /tmp/netcoin-qa --json
```

## Important security note

Do not commit `deploy/deploy.env` if it contains secrets or private infrastructure details.
Use `deploy/deploy.env.example` as the committed template.
