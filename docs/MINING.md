# Mining NetCoin From Your Own Machine

This guide shows how to mine NetCoin testnet blocks from your own computer and
submit them to the public network. It uses the built-in external miner, the same
workflow public testers used to mine blocks 103–105.

> Educational testnet. Block rewards are testnet NET with no real-money value.
> Mining difficulty is intentionally low so a laptop can find blocks.

## How NetCoin mining works (short version)

1. You ask a node for a **block template** (`/blocktemplate`).
2. The miner builds a candidate block paying the reward to **your** address and
   searches for a nonce that satisfies the proof-of-work target.
3. You **submit** the solved block back to a node (`/submitblock`), which validates
   it and relays it to peers.

Coinbase rewards are spendable only after **100 confirmations** (coinbase
maturity).

## 1. Create a mining wallet

Keep your mining wallet separate and back it up.

```bash
python -m netcoin wallet-new --out miner.json --mnemonic
chmod 600 miner.json
python -m netcoin wallet-info --wallet miner.json
```

Note the address — that's where rewards are paid.

## 2. Mine against a public seed

The simplest path is to point the miner straight at a public seed node:

```bash
python -m netcoin miner \
  --node http://seed1.netcoin.online:28444 \
  --wallet miner.json \
  --blocks 1
```

- `--blocks N` mines up to N blocks then stops.
- Use the raw seed IPs (`18.220.89.128`, `18.220.197.20`, `18.226.74.252`) if the
  hostname is blocked on your network.
- Spread load: mine against `seed1` one round, `seed2` the next, etc.

On success the node advances its height and relays your block to the other seeds.

## 3. Mine against your own node (recommended)

Better practice: run your own node (see [NODE_RUNNER.md](NODE_RUNNER.md)) and mine
against `127.0.0.1`. Your node relays solved blocks to the seeds for you.

```bash
# terminal 1: your synced node
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444

# terminal 2: mine to your local node
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json --blocks 5
```

## 4. Two-step mining (save then submit)

You can solve blocks and keep the JSON to submit later or from another machine.
The miner writes each solved block into the directory given by `--save-blocks`:

```bash
# solve and save solved block JSON files (also submits them to --node)
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json \
  --blocks 1 --save-blocks ./solved

# submit a previously solved block to any node
python -m netcoin submitblock ./solved/<block-file>.json --node http://seed1.netcoin.online:28444
```

To just *inspect* the next block's template locally (no solving, no network):

```bash
python -m netcoin template --wallet miner.json
```

## 5. Check your rewards

```bash
python -m netcoin balance \
  --node http://18.220.89.128:28444 \
  --address <YOUR_ADDRESS>
```

This can query any public seed. If you run your own synced node/data directory, this
also works locally:

```bash
python -m netcoin --data ~/.netcoin-testnet balance --address <YOUR_ADDRESS>
```

You'll see `immature` reward until 100 blocks pass, then it becomes `spendable`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `block does not connect to current tip` | someone else mined first | re-fetch a template and try again; the miner does this automatically |
| Submit returns the same hash twice | duplicate submission | harmless — block relay is idempotent |
| Reward stays `immature` | coinbase maturity | wait 100 confirmations |
| Miner can't reach node | wrong URL / node down | check `curl <node>/info` |

## Etiquette

- Don't hammer a single seed with a long `--blocks` run; rotate seeds or mine to
  your own node.
- This is a shared testnet — leave room for other testers to find blocks.
- Never share or commit `miner.json`; it controls your rewards.

See also: [NODE_RUNNER.md](NODE_RUNNER.md) and [STARTER_KIT.md](STARTER_KIT.md).
