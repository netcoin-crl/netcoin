# Upgrading NetCoin

How to update a node from one release to the next (e.g. v0.4.0 → v0.4.1) without
wiping chain data or wallets.

> NetCoin uses Semantic Versioning. PATCH and MINOR upgrades keep existing testnet
> data and wallet files compatible. A MAJOR upgrade (e.g. 0.x → 1.0) may change the
> chain or wallet format and will ship explicit migration notes here.

## Data that must survive an upgrade

- Chain data: the `--data` directory (default `~/.netcoin-testnet`, or
  `/opt/netcoin/.netcoin-testnet` on seeds) — `chain.json`, `mempool.json`,
  `peers.json`.
- Wallet files (`*.json`) and the faucet wallet — never overwrite these.
- Service unit files, explorer output, monitor config.

The upgrade replaces **source code only**, not the data directory.

## Before you upgrade

1. Read the [CHANGELOG](../CHANGELOG.md) for the target version — note anything
   under "Breaking" or migration notes.
2. Back up first:
   ```bash
   tools/backup_node.sh
   ```

## Upgrade on a seed (scripted, with rollback)

`tools/deploy_seed.sh` backs up, swaps the source, reinstalls, runs the tests,
restarts the service, and **rolls back automatically** if the tests or the
`/info` health check fail:

```bash
# from a directory containing the new source
sudo tools/deploy_seed.sh --source /path/to/new/netcoin-v2
# or from a release zip
sudo tools/deploy_seed.sh --zip /path/to/netcoin-v2-public-testnet-ready.zip
```

## Upgrade manually

```bash
# 1. stop the node
sudo systemctl stop netcoin-node.service

# 2. back up
tools/backup_node.sh

# 3. replace the source (keep the same --data dir!)
#    e.g. unzip the new release over /opt/netcoin/netcoin-v2

# 4. reinstall the package
/opt/netcoin/netcoin-v2/.venv/bin/python -m pip install -e /opt/netcoin/netcoin-v2

# 5. run the tests
( cd /opt/netcoin/netcoin-v2 && .venv/bin/python -m pytest -q )

# 6. restart and verify
sudo systemctl start netcoin-node.service
curl -fsS http://127.0.0.1:28444/info
```

## Verify after upgrade

- `/info` returns JSON with the expected `protocol_version`.
- Height and tip match the other seeds (or catch up shortly via sync).
- `python -m pytest` passes.

## Rolling back

If something is wrong, restore the source (and, only if necessary, the data) from
the backup archive produced in step 2, then restart the service. Because data and
source are separate, a code rollback alone usually fixes a bad upgrade without
touching chain data.

## Protocol/version bumps

If a release changes `PROTOCOL_VERSION` or the chain/wallet format, this section
lists the exact migration steps.

- **Chain data:** no migration is required across the 0.2.x → 0.4.x line — the
  genesis block and `PROTOCOL_VERSION` are unchanged, so existing `--data`
  directories keep working. (Optionally switch a node to the SQLite backend with
  `migrate-sqlite`; see docs/OPERATIONS.md.)
- **Wallet files (v0.4.x):** wallet files now carry a `wallet_version`, and
  encrypted wallets use a stronger KDF. Older wallets still open as-is. To upgrade
  one in place (re-encrypt at the new KDF cost, stamp the version, back up the
  original first):
  ```bash
  python -m netcoin wallet-migrate --wallet my-wallet.json --passphrase '<your pass>'
  ```
- **Blocks with witness data (v0.4.1):** SegWit-style witness commitment applies
  only to blocks that contain witness transactions; no action is needed for
  existing data.
