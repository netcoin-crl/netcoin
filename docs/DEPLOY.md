# Deploying the node (git-sourced)

Goal: production always matches a committed git ref, and node code is **never**
edited directly on a server. (Editing on-server previously hid a crash bug and a
seed version skew.)

## One-time per seed
Add read access to the private repo (a GitHub **deploy key** is simplest), then:

```bash
sudo git clone git@github.com:netcoin-crl/netcoin.git /opt/netcoin/netcoin-git
```

The deploy scripts prefer a managed **Python 3.13** runtime through `uv` and
install NetCoin with `.[test,fast]`, which includes `coincurve`/libsecp256k1
signature verification. This avoids Ubuntu 26.04's default Python 3.14 until the
fast-crypto wheel/build path is clean there.

## Every deploy (run on each seed, one at a time)
```bash
sudo /opt/netcoin/netcoin-v2/tools/deploy_node_from_git.sh main   # or a tag, e.g. v0.12.0
```
The script fetches the ref, **runs the test suite as a gate**, backs up the
current node package, syncs `netcoin/` + `pyproject.toml` from git (leaving the
site/app files in place), reinstalls into Python 3.13, ensures
`NETCOIN_FAST_CRYPTO=1`, restarts the node, and health-checks `/info`. Roll
seeds one at a time and confirm each is on the new version and in consensus
before the next.

Expected healthy public-node crypto metadata:

```json
{
  "ecdsa_verify": "libsecp256k1/coincurve",
  "fast_crypto_enabled": true
}
```

Override knobs:

```bash
NETCOIN_DEPLOY_PYTHON=3.13          # default
NETCOIN_ENABLE_FAST_CRYPTO=1        # default; set 0 for pure-Python fallback
```

## Consensus changes
Any change to block rewards / validation (e.g. the emission schedule) must reach
**every seed and miner before the activation height**, or nodes fork. The seeds
share the same code via this flow; external miners must update independently.

## Alternative: reproducible artifact
`tools/make_release.sh <ref>` builds a signed, reproducible zip from a git ref;
`tools/deploy_seed.sh --zip <file>` installs it. Use this when a seed can't pull
the repo directly.
