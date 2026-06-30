# NetCoin node reliability and load-reduction plan

This document describes the public-node safeguards added for the v0.7.5 reliability update.

## Why this exists

A public node may serve several roles at once: seed discovery, wallet API, explorer API, mining templates, transaction relay, and faucet/merchant support. A single oversized transaction or heavy explorer page should not make the node feel frozen.

## Added protections

- Wallet send pre-checks before signing/broadcasting.
- Maximum wallet-send input count.
- Maximum wallet-send transaction weight.
- Clear insufficient-balance and immature-coin messages.
- Browser send timeout handling and Send button re-enable after errors.
- Mempool expiry for stale unconfirmed transactions.
- Mempool count/byte policy information.
- Mempool clear/info CLI commands for operators.
- `/health` and `/status-lite` fast node-health endpoints.
- Short response caching for read-heavy `/info`, `/health`, and `/latest`.
- Address history pagination using `limit` and `offset` query parameters.
- Miner request timeout option.

## Operator commands

Show public node health:

```bash
curl -s http://127.0.0.1:28444/health
```

Show mempool policy and usage:

```bash
python -m netcoin mempool-info --node http://127.0.0.1:28444 --summary
```

Clear local unconfirmed mempool safely:

```bash
python -m netcoin --data /opt/netcoin/.netcoin-testnet mempool-clear
sudo systemctl restart netcoin-node
```

Confirmed blocks and UTXOs are not deleted by clearing the mempool. Mempool transactions are pending/unconfirmed state.

## Mining recommendation

Mine one block at a time while the public testnet is small:

```bash
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --timeout 60
```

Avoid `--sync-after` unless you specifically need it, because extra peer sync work can make the command appear slow even after a block was accepted.

## Seed vs API role split

Long term, keep public seeds boring and stable:

- `seed*.netcoin.online`: seed/full-node sync and peer discovery.
- `api.netcoin.online`: wallet/API traffic.
- `explorer.netcoin.online`: static frontend and cached explorer reads.
- `nodes.netcoin.online`: node/seed status dashboard.



## Large send or timeout troubleshooting

If a wallet send times out after trying a large amount, check the mempool and node health before trying again:

```bash
curl -s http://18.220.89.128/api/health
python -m netcoin mempool-info --node http://18.220.89.128/api --summary
```

Mine one block at a time while testing:

```bash
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --timeout 60
```

Avoid sending almost your full balance until the wallet shows the transaction preview as safe.
