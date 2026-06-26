# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in
pure Python. It runs on macOS, Linux, and Windows with Python 3.10+.

NetCoin is **not Bitcoin**, does not connect to the Bitcoin network, and should
not be used as real money software. Public testnet NET has no real-money value.

> Current release: **v0.6.0**

## Start Here: Public Testnet

Most users should start by connecting to the public NetCoin testnet. The commands
below use the public AWS seed IPs because some home networks block the
`seed*.netcoin.online` hostnames.

Public nodes:

```text
seed1.netcoin.online:28444 -> http://18.220.89.128:28444
seed2.netcoin.online:28444 -> http://18.220.197.20:28444
seed3.netcoin.online:28444 -> http://18.226.74.252:28444
```

Quick health check:

macOS / Linux:

```bash
curl http://18.220.89.128:28444/info
curl http://18.220.197.20:28444/health
curl "http://18.226.74.252:28444/latest?n=5"
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://18.220.89.128:28444/info
Invoke-RestMethod http://18.220.197.20:28444/health
Invoke-RestMethod "http://18.226.74.252:28444/latest?n=5"
```

## 1. Install

macOS / Linux:

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m netcoin --help
```

Windows PowerShell:

```powershell
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m netcoin --help
```

Run commands from the project folder, the one with `pyproject.toml`.

## 2. Create A Wallet

```bash
python -m netcoin wallet-new --out miner.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet miner.json
```

Write down the recovery phrase. The wallet file controls your testnet coins.

## 3. Mine On The Public Network

Mine one block:

```bash
python -m netcoin miner --node http://18.220.89.128:28444 --wallet miner.json --blocks 1
```

Mine continuously until you stop it with `Ctrl+C`:

macOS / Linux:

```bash
while true; do
  python -m netcoin miner --node http://18.220.197.20:28444 --wallet miner.json --blocks 1
done
```

Windows PowerShell:

```powershell
while ($true) {
  python -m netcoin miner --node http://18.220.197.20:28444 --wallet miner.json --blocks 1
}
```

Rotate seeds when mining so one seed does not take all the traffic:

```bash
python -m netcoin miner --node http://18.220.89.128:28444  --wallet miner.json --blocks 1
python -m netcoin miner --node http://18.220.197.20:28444  --wallet miner.json --blocks 1
python -m netcoin miner --node http://18.226.74.252:28444 --wallet miner.json --blocks 1
```

Mining rewards are coinbase rewards. They show as `immature` until 100 more
blocks are mined after them.

## 4. Check Balance

Check your wallet:

```bash
python -m netcoin balance --node http://18.220.89.128:28444 --wallet miner.json
```

Check any address:

```bash
python -m netcoin balance --node http://18.220.89.128:28444 --address <NETCOIN_ADDRESS>
```

Show your addresses:

```bash
python -m netcoin wallet-info --wallet miner.json
```

## 5. Run A Public Seed

Use this when other people should be able to connect to your node.

On a VPS or public server:

macOS / Linux:

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 0.0.0.0 \
  --port 28444 \
  --p2p-port 18447 \
  --sync-interval 60 \
  --rate-limit-per-min 240 \
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 \
  --peer http://18.220.89.128:28444 \
  --peer http://18.220.197.20:28444 \
  --peer http://18.226.74.252:28444
```

Windows PowerShell:

```powershell
python -m netcoin --data ~/.netcoin-testnet node `
  --host 0.0.0.0 `
  --port 28444 `
  --p2p-port 18447 `
  --sync-interval 60 `
  --rate-limit-per-min 240 `
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 `
  --peer http://18.220.89.128:28444 `
  --peer http://18.220.197.20:28444 `
  --peer http://18.226.74.252:28444
```

Open these inbound firewall/security-group ports:

| Port | Purpose | Public? |
| --- | --- | --- |
| `28444` | HTTP node API | yes |
| `18447` | experimental binary P2P | yes, optional |
| `28445` | JSON-RPC | no |
| `28446` | pool/template server | no |

Keep RPC and pool ports private. Do not expose wallet files, seed phrases, private
keys, server keys, or RPC tokens.

NetCoin ignores `X-Forwarded-For` by default so direct public clients cannot spoof
IP addresses to bypass rate limits. Only add `--trust-proxy-headers` when the node
is behind a reverse proxy you control.

No-port-forwarding options are in
[docs/PUBLIC_SEED_HOSTING.md](docs/PUBLIC_SEED_HOSTING.md).

## 6. Use The Browser Wallet

This is the easiest way to view a wallet and send transactions.

```bash
python -m netcoin web --node http://18.220.89.128:28444
```

Open this in your browser:

```text
http://127.0.0.1:8088/
```

The web wallet is local. Your private keys stay on your computer. It only sends
signed transactions to the public node.

## 7. Run Your Own Public-Testnet Node

This runs a node on your computer, syncs with the public seeds, and lets you mine
through your own node instead of directly hitting the AWS seeds.

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://18.220.89.128:28444 --peer http://18.220.197.20:28444 --peer http://18.226.74.252:28444
```

Check your node:

macOS / Linux:

```bash
curl http://127.0.0.1:28444/info
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:28444/info
```

Mine through your own node:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json --blocks 1
```

You can also use the built-in seed list:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --seeds
```

If your network blocks `seed*.netcoin.online`, use the raw-IP `--peer` command
above.

## 8. Send Coins

Use the local browser wallet for the simplest public-network send flow:

```bash
python -m netcoin web --node http://18.220.89.128:28444
```

Then open:

```text
http://127.0.0.1:8088/
```

For local/private CLI practice, see the next section.

## Local Practice Chain

These commands make a private chain on your computer. They do **not** connect to
the public NetCoin testnet.

```bash
python -m netcoin --data demo-chain init
python -m netcoin wallet-new --out local-miner.json --mnemonic --confirm-backup
python -m netcoin wallet-new --out local-alice.json
python -m netcoin --data demo-chain mine --wallet local-miner.json --blocks 101
python -m netcoin --data demo-chain balance --wallet local-miner.json
```

Send locally:

macOS / Linux:

```bash
ALICE=$(python -m netcoin wallet-info --wallet local-alice.json | python -c 'import json,sys; print(json.load(sys.stdin)["address"])')
python -m netcoin --data demo-chain send --wallet local-miner.json --to "$ALICE" --amount 12.5 --fee 0.01
python -m netcoin --data demo-chain mine --wallet local-miner.json --blocks 1
python -m netcoin --data demo-chain balance --wallet local-alice.json
```

Windows PowerShell:

```powershell
$aliceInfo = python -m netcoin wallet-info --wallet local-alice.json | ConvertFrom-Json
$alice = $aliceInfo.address
python -m netcoin --data demo-chain send --wallet local-miner.json --to $alice --amount 12.5 --fee 0.01
python -m netcoin --data demo-chain mine --wallet local-miner.json --blocks 1
python -m netcoin --data demo-chain balance --wallet local-alice.json
```

## Explorer

Run a local explorer for a synced node:

```bash
python -m netcoin --data ~/.netcoin-testnet explorer-server --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/
```

Generate a static explorer for a local/private chain:

```bash
python -m netcoin --data demo-chain explorer --out explorer
open explorer/index.html
```

Linux:

```bash
xdg-open explorer/index.html
```

Windows PowerShell:

```powershell
Start-Process .\explorer\index.html
```

## Light Client Tools

Scan a wallet with compact filters:

```bash
python -m netcoin scan-filters --node http://18.220.89.128:28444 --wallet miner.json
```

Fetch a block filter:

```bash
python -m netcoin blockfilter --node http://18.220.89.128:28444 --height 100
```

## Local RPC

Keep RPC private:

```bash
python -m netcoin --data ~/.netcoin-testnet rpc --host 127.0.0.1 --port 28445
python -m netcoin rpc-call getblockchaininfo --url http://127.0.0.1:28445
```

Optional token:

macOS / Linux:

```bash
NETCOIN_RPC_TOKEN="choose-a-secret" \
python -m netcoin --data ~/.netcoin-testnet rpc --host 127.0.0.1 --port 28445
```

Windows PowerShell:

```powershell
$env:NETCOIN_RPC_TOKEN = "choose-a-secret"
python -m netcoin --data ~/.netcoin-testnet rpc --host 127.0.0.1 --port 28445
```

## What Is Implemented

Core chain:

- UTXO chain validation
- Real proof-of-work mining
- 2-minute target blocks with difficulty retargeting
- Testnet lone-miner rule so the chain can keep moving
- Merkle roots
- Coinbase rewards and 100-block coinbase maturity
- secp256k1 ECDSA signatures
- BIP340-style Schnorr signatures for Taproot-like key-path spends
- Legacy, P2SH-SegWit, SegWit-style, and Taproot-style addresses
- Educational Script engine
- P2PKH, P2SH, P2WPKH, P2WSH, and P2TR script templates
- Multisig helpers
- Timelock helpers
- Transaction locktime and sequence handling
- Opt-in RBF signaling
- Mempool policy limits
- Block weight limit
- Raw Bitcoin-style transaction and block hex export
- SegWit-style txid/wtxid split

Network:

- HTTP node API
- Experimental binary TCP P2P server/client
- Headers-first sync shape
- Compact-block summaries
- BIP158-style compact block filters
- Relay queue and peer inventory cache
- Cumulative-work fork choice
- Reorg, rollback, and mempool revalidation
- Orphan block candidate handling
- Public endpoint rate limiting

Wallet and tools:

- Encrypted wallet files
- Deterministic NetCoin seed phrases
- HD wallet derivation
- Watch-only wallet files
- Descriptor helpers
- PSBT-like signing flow
- Local web wallet
- API-backed explorer server
- JSON-RPC server
- Mining-pool template server
- Faucet hardening support
- Signed messages
- Payment URIs
- Local multi-node soak/stress harness
- Deterministic fuzz smoke runner
- Reindex and crash-safe JSON persistence
- Optional SQLite backend
- Pruned mode

Still not something code alone can create:

- Real global hashpower
- A worldwide independent node network
- Exchange listings
- Real liquidity
- Hardware wallet vendor support
- A production security review
- A public user ecosystem

Those require people, infrastructure, review, miners, users, and time.

## Project Guides

- [docs/GUIDE.md](docs/GUIDE.md) - complete step-by-step guide
- [docs/STARTER_KIT.md](docs/STARTER_KIT.md) - 10-minute first run
- [docs/MINING.md](docs/MINING.md) - mining from your own machine
- [docs/NODE_RUNNER.md](docs/NODE_RUNNER.md) - independent full node guide
- [docs/PUBLIC_SEED_HOSTING.md](docs/PUBLIC_SEED_HOSTING.md) - public seed hosting
- [docs/TESTNET.md](docs/TESTNET.md) - public testnet layout
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - architecture and data flows
- [docs/OPERATIONS.md](docs/OPERATIONS.md) - backups, monitoring, logs, deployment
- [docs/UPGRADING.md](docs/UPGRADING.md) - update a node safely
- [docs/RELEASING.md](docs/RELEASING.md) - signed releases and checksums
- [docs/SECURITY_TESTING.md](docs/SECURITY_TESTING.md) - abuse/crash/replay tests
- [docs/SECURITY_REVIEW_PLAN.md](docs/SECURITY_REVIEW_PLAN.md) - external review checklist
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md) - what NetCoin is not

## Developer Checks

Run tests:

```bash
python -m pytest -q
```

Run a local multi-node soak test:

```bash
python -m netcoin soak --nodes 3 --rounds 3
```

Run fuzz smoke tests:

```bash
python -m netcoin fuzz --iterations 100
```

## Safety

This is learning software. It has readable pure-Python cryptography and simplified
networking so you can study it. It is not hardened like Bitcoin Core.

Do not promote it as Bitcoin. Do not imply it is affiliated with Bitcoin. Do not
use the included wallet files for real value.
