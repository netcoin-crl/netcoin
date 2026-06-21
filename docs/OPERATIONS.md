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

See [docs/UPGRADING.md](UPGRADING.md) for the full upgrade/rollback flow.
