# Deploying the node (git-sourced)

Goal: production always matches a committed git ref, and node code is **never**
edited directly on a server. (Editing on-server previously hid a crash bug and a
seed version skew.)

## One-time per seed
Add read access to the private repo (a GitHub **deploy key** is simplest), then:

```bash
sudo git clone git@github.com:netcoin-crl/netcoin.git /opt/netcoin/netcoin-git
```

## Every deploy (run on each seed, one at a time)
```bash
sudo /opt/netcoin/netcoin-v2/tools/deploy_node_from_git.sh v0.7.7   # tag or 'main'
```
The script fetches the ref, **runs the test suite as a gate**, backs up the
current node package, syncs `netcoin/` + `pyproject.toml` from git (leaving the
site/app files in place), reinstalls, restarts the node, and health-checks
`/info`. Roll seeds one at a time and confirm each is on the new version and in
consensus before the next.

## Consensus changes
Any change to block rewards / validation (e.g. the emission schedule) must reach
**every seed and miner before the activation height**, or nodes fork. The seeds
share the same code via this flow; external miners must update independently.

## Alternative: reproducible artifact
`tools/make_release.sh <ref>` builds a signed, reproducible zip from a git ref;
`tools/deploy_seed.sh --zip <file>` installs it. Use this when a seed can't pull
the repo directly.
