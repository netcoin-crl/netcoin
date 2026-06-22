# NetCoin Operations Guide

Running NetCoin seeds and services day to day: logging, log rotation, backups,
and deploying tagged releases.

## Structured logging

Services emit structured JSON log lines when `NETCOIN_LOG_JSON=1` is set; otherwise
they keep human-readable output. JSON lines are one object per line:

```bash
NETCOIN_LOG_JSON=1 python -m netcoin --data ~/.netcoin-testnet node --seeds
# {"component":"node","event":"block_accepted","hash":"...","height":106,"ts":...}
```

In a systemd unit, add it to the service environment:

```ini
[Service]
Environment=NETCOIN_LOG_JSON=1
```

Logs go to stderr, so `journalctl -u netcoin-node.service` captures them.

## Log rotation

If you redirect logs to files instead of journald, rotate them so they don't fill
the disk. Example `/etc/logrotate.d/netcoin`:

```
/opt/netcoin/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

With journald, set retention instead (e.g. `SystemMaxUse=500M` in
`/etc/systemd/journald.conf`). The monitor's `status.json` is overwritten in place
and does not grow.

## Backups

Run `tools/backup_node.sh` (see also docs/UPGRADING.md). It archives chain data,
wallets, faucet state, peer/ban files, systemd units, explorer, and monitor config
into a single private `.tar.gz`. Schedule it from cron:

```
0 3 * * * /opt/netcoin/netcoin-v2/tools/backup_node.sh /opt/netcoin/backups
```

## Crash safety & recovery

The default JSON backend writes `chain.json` / `mempool.json` crash-safely: each
save goes to an fsync'd temp file, is atomically renamed into place, and a `.bak`
mirror of the last committed state is kept. On startup a corrupt live file is
recovered from `.bak` (or a leftover `.tmp`) without losing the most recent block;
a corrupt `mempool.json` is simply dropped (the mempool is non-consensus state).

To rebuild the indexes and UTXO set from block data — e.g. after a forced kill,
disk scare, or moving data between machines — run a reindex, which also runs a
chainstate integrity check:

```
python -m netcoin --data <DATA_DIR> reindex
# {"ok": true, "reindexed": true, "integrity": {"index_consistent": true, ...}}
```

## Deploying a tagged release (not the working tree)

Build a release artifact from a tag, copy it to the seed, then deploy it with
rollback via `tools/deploy_seed.sh --zip`:

```bash
# on a build machine / locally
git fetch --tags
tools/make_release.sh v0.3.1                 # -> dist/netcoin-0.3.1.zip + SHA256SUMS
scp dist/netcoin-0.3.1.zip user@seed1:/opt/netcoin/

# on the seed (as root/sudo)
cd /opt/netcoin/netcoin-v2
sudo tools/deploy_seed.sh --zip /opt/netcoin/netcoin-0.3.1.zip
```

`deploy_seed.sh` backs up first, swaps the source, reinstalls, runs the tests,
restarts the service, and **rolls back automatically** if tests or the `/health`
check fail. Always deploy a checksummed release artifact rather than a raw working
tree so every seed runs an identical, verifiable build.

## Health & metrics

- `curl http://127.0.0.1:28444/health` — quick status (height, tip, peers, uptime).
- `curl http://127.0.0.1:28444/metrics` — Prometheus metrics.
- `curl http://127.0.0.1:28444/events` — recent block-propagation events.

## Local soak/stress checks

Before tagging or deploying a networking change, run the bounded in-process soak
harness. It starts multiple local HTTP nodes, connects them as peers, mines mature
funds, relays transactions and blocks, forces sync, and fails if tips diverge:

```bash
python -m netcoin soak --nodes 3 --rounds 5 --transactions-per-round 2
```

For a longer manual run, increase `--rounds` and optionally keep data with
`--dir /tmp/netcoin-soak-run`.

## Local fuzz smoke

Run deterministic parser and endpoint fuzz smoke under Python dev mode before a
release candidate:

```bash
python -X dev -m netcoin fuzz --target all --iterations 1000 --max-bytes 256
```

CI runs a shorter `fuzz-smoke` job. This is a lightweight safety net, not a
replacement for deep coverage-guided fuzzing or native sanitizer infrastructure.

See [docs/UPGRADING.md](UPGRADING.md) for the full upgrade/rollback flow.
