# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in pure Python. It is **not Bitcoin**, does not connect to the Bitcoin network, and should not be used as real money software.

It runs anywhere Python 3.10+ runs — **macOS, Linux, and Windows** — with **no third-party dependencies** (standard library only). The public testnet seeds run it on Ubuntu Linux.

> **Current release: v0.4.2.** See the [CHANGELOG](CHANGELOG.md) for what each release added and [docs/UPGRADING.md](docs/UPGRADING.md) for updating a node between releases.

## What's implemented

Core chain and consensus (since v0.2):

- UTXO chain validation
- Proof-of-work mining
- Merkle roots
- Coinbase rewards and 100-block coinbase maturity
- 21,000,000 NET monetary cap through 210,000-block halvings
- secp256k1 ECDSA signatures
- Base58Check legacy addresses
- Bech32 SegWit-style P2WPKH addresses
- Bech32m Taproot-style P2TR addresses
- BIP340-style Schnorr signatures for Taproot-like key-path spends
- Text-based educational NetCoin Script engine
- P2PKH, P2SH, P2WPKH, P2WSH, P2TR script templates
- Multisig redeem-script helpers
- CLTV/CSV-style timelock script helpers
- Transaction locktime and sequence handling
- Opt-in RBF signaling
- Mempool policy: dust, min relay fee, weight, and ancestor-style limits
- Block weight limit
- Raw Bitcoin-style transaction/block hex export
- SegWit-style txid/wtxid split
- Headers endpoint for headers-first sync shape
- Compact-block summary endpoint
- Orphan block candidate handling
- JSON-RPC server
- Mining-pool template server
- Static HTML block explorer generator
- API-backed explorer server
- Encrypted wallet files
- Deterministic NetCoin seed phrases
- Watch-only wallet files
- Main/testnet/signet/regtest profile descriptions
- P2P message envelope framing helpers and experimental TCP P2P server/client
- PSBT-like signing container

Added in v0.3–v0.4:

- Persistent/incremental UTXO set (no full rescan per query)
- Pruned mode (drop old block bodies, keep headers + UTXO snapshot)
- Persistent block / transaction / address indexes
- Optional SQLite storage backend (`NETCOIN_BACKEND=sqlite`) with `migrate-sqlite`
- Cumulative-work fork choice with reorg, rollback, and mempool revalidation
- Headers-first sync, relay queue, and peer inventory cache over the TCP transport
- Fuller Script VM (conditionals, arithmetic, stack ops, crypto opcodes, strict errors)
- Full PSBT flow (create / sign / combine / finalize / extract)
- Descriptor wallets (`wallet-descriptor`, `descriptor-address`)
- Wallet format versioning + migration (`wallet-migrate`) and a stronger KDF
- Coin control / selection strategies, gap-limit scan, labels, change-address rotation, auto-lock
- Faucet hardening (rate limits, abuse log, send queue, hot-wallet isolation)
- Versioned release process with reproducible artifacts + `SHA256SUMS`
- Local multi-node soak/stress harness (`soak`) for relay/sync convergence checks
- Deterministic parser/endpoint fuzz smoke runner (`fuzz`)

Still not something code alone can create:

- Real global hashpower
- A worldwide node network
- Exchange listings
- Real liquidity
- Hardware wallet vendor support
- A production security review
- A public user ecosystem

Those require people, infrastructure, review, miners, users, and time.

## Get the code & run it

NetCoin has no external Python package dependencies. Clone the repo and run it from the project root (the folder that contains `pyproject.toml`):

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m netcoin --help
```

Optional virtual environment (recommended):

```bash
cd netcoin
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m netcoin --help
```

The inner `netcoin/` folder is the Python package — run commands from the project root, not from inside it.

> Works on macOS, Linux, and Windows. The CLI is pure Python; the `tools/*.sh` operator
> scripts are bash (macOS/Linux/WSL) and the systemd units are Linux-only. A few examples
> below use the macOS `open` command — substitute `xdg-open` (Linux) or `start` (Windows).

## Public testnet status

NetCoin is in a **testnet-only** phase. Testnet NET has no real-money value, bugs are expected, and seed nodes should expose only the public peer port.

Default public testnet ports:

- Peer/node HTTP: `28444`
- JSON-RPC: `28445` local/private only
- Pool/template server: `28446` local/private only
- Experimental TCP P2P: `28447`

The first public milestone is a single seed node that returns JSON:

```bash
curl http://SEED1_IP:28444/info
```

Current public testnet seeds:

```text
seed1.netcoin.online:28444
seed2.netcoin.online:28444
seed3.netcoin.online:28444
```

See [docs/TESTNET.md](docs/TESTNET.md) for the Mac-to-Ubuntu seed-node checklist, systemd unit, DNS layout, public user instructions, explorer notes, faucet requirements, monitoring, and launch order.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the current public testnet architecture, component layout, data flows, trust boundaries, weak spots, and target network shape.

See [docs/SECURITY_TESTING.md](docs/SECURITY_TESTING.md) for malformed block, bad transaction, faucet abuse, node crash, replay, and public endpoint limit testing.

### Guides for testers

- [docs/STARTER_KIT.md](docs/STARTER_KIT.md) — 10-minute from-scratch walkthrough: install, wallet, faucet, send, mine, report bugs.
- [docs/NODE_RUNNER.md](docs/NODE_RUNNER.md) — run your own independent full node and peer with the public seeds.
- [docs/MINING.md](docs/MINING.md) — mine testnet blocks from your own machine and submit them.
- [docs/RELEASING.md](docs/RELEASING.md) — versioning, signed release artifacts, and how users verify downloads.
- [docs/UPGRADING.md](docs/UPGRADING.md) — update a node between releases without wiping data (with rollback).
- [docs/SECURITY_REVIEW_PLAN.md](docs/SECURITY_REVIEW_PLAN.md) — the external-review checklist that gates any mainnet discussion.

Operator tooling lives in `tools/`: `backup_node.sh` (backup), `deploy_seed.sh` (safe
update with rollback), `dashboard.py` (public status page), `faucet_admin.py` (private
faucet admin view), and `monitor_netcoin.py` (status + optional webhook alerts). The
faucet exposes `/history`, `/queue`, `/status`, and an admin-token-protected
`/admin/process-queue` endpoint for queued payouts and hot-wallet refill checks.
The node also exposes explorer-style JSON: `/tx/<txid>`, `/address/<address>`,
`/balance/<address>`, `/latest?n=`, `/utxos?address=`, `/block/<hash>`,
`/mempool`, and `/relay` for relay-queue visibility.

> The JSON-RPC server supports optional bearer-token auth: pass `--rpc-token` (or set
> `NETCOIN_RPC_TOKEN`) and keep it bound to `127.0.0.1`. The node and RPC servers also
> cap request body size to blunt trivial memory-DoS attempts. Public node and explorer
> HTTP endpoints support `--rate-limit-per-min` (`0` disables) for per-IP/per-path
> throttling.

## Quick start

```bash
python -m netcoin --data demo-chain init
python -m netcoin wallet-new --out miner.json --mnemonic
python -m netcoin wallet-new --out alice.json
python -m netcoin --data demo-chain mine --wallet miner.json --blocks 101
python -m netcoin --data demo-chain balance --wallet miner.json
```

Check any address against a public seed:

```bash
python -m netcoin balance \
  --node http://18.220.89.128:28444 \
  --address <NETCOIN_ADDRESS>
```

Send to Alice's SegWit-style address:

```bash
ALICE_SEGWIT=$(python -m netcoin wallet-info --wallet alice.json | python -c 'import json,sys; print(json.load(sys.stdin)["addresses"]["segwit"])')
python -m netcoin --data demo-chain send --wallet miner.json --to "$ALICE_SEGWIT" --amount 12.5 --fee 0.01 --rbf
python -m netcoin --data demo-chain mine --wallet miner.json --blocks 1
python -m netcoin --data demo-chain balance --wallet alice.json --address-type p2wpkh
python -m netcoin --data demo-chain validate
```

Mine and spend Taproot-style outputs:

```bash
python -m netcoin --data taproot-chain init
python -m netcoin wallet-new --out tr-miner.json
python -m netcoin wallet-new --out tr-alice.json
python -m netcoin --data taproot-chain mine --wallet tr-miner.json --address-type p2tr --blocks 101

ALICE_TR=$(python -m netcoin wallet-info --wallet tr-alice.json | python -c 'import json,sys; print(json.load(sys.stdin)["addresses"]["taproot"])')
python -m netcoin --data taproot-chain send --wallet tr-miner.json --from-type p2tr --to "$ALICE_TR" --amount 3 --fee 0.01
python -m netcoin --data taproot-chain mine --wallet tr-miner.json --address-type p2tr --blocks 1
python -m netcoin --data taproot-chain balance --wallet tr-alice.json --address-type p2tr
```

## Useful commands

Show all address types:

```bash
python -m netcoin wallet-info --wallet miner.json
```

Show the Script template for an address:

```bash
ADDR=$(python -m netcoin wallet-info --wallet miner.json | python -c 'import json,sys; print(json.load(sys.stdin)["addresses"]["taproot"])')
python -m netcoin script "$ADDR"
```

Show mempool policy data:

```bash
python -m netcoin --data demo-chain mempool
python -m netcoin --data demo-chain fee
```

Show headers and raw block data:

```bash
python -m netcoin --data demo-chain headers --limit 5
python -m netcoin --data demo-chain rawblock tip
```

Generate a static explorer:

```bash
python -m netcoin --data demo-chain explorer --out explorer
open explorer/index.html
```

Run the live API-backed explorer:

```bash
python -m netcoin --data demo-chain explorer-server --host 127.0.0.1 --port 8080
open http://127.0.0.1:8080/
```

Run a local peer node:

```bash
python -m netcoin --data node-a node --host 127.0.0.1 --port 18444
```

Mine through a running node instead of writing directly to a local chain:

```bash
python -m netcoin wallet-new --out miner.json --mnemonic
python -m netcoin miner \
  --node http://seed1.netcoin.online:28444 \
  --wallet miner.json \
  --blocks 1
```

Save solved block JSON while mining:

```bash
python -m netcoin miner \
  --node http://seed1.netcoin.online:28444 \
  --wallet miner.json \
  --blocks 1 \
  --save-blocks solved-blocks
```

Submit a saved solved block:

```bash
python -m netcoin submitblock solved-blocks/block-HEIGHT-HASH.json \
  --node http://seed1.netcoin.online:28444
```

Run a JSON-RPC server:

```bash
python -m netcoin --data demo-chain rpc --host 127.0.0.1 --port 18445
```

Call RPC from another terminal:

```bash
python -m netcoin rpc-call getblockchaininfo --url http://127.0.0.1:18445
python -m netcoin rpc-call getrawmempool --params '[true]' --url http://127.0.0.1:18445
```

Run the educational mining-pool template server:

```bash
python -m netcoin --data demo-chain pool --wallet miner.json --host 127.0.0.1 --port 18446
```

## Safety warning

This is learning software. It has readable pure-Python cryptography and simplified networking so you can study it. It is not hardened against timing attacks, network attacks, denial-of-service, chain-split edge cases, wallet theft, or adversarial miners.

Do not promote it as Bitcoin. Do not imply it is affiliated with Bitcoin. Do not use the included wallet files for real value.
