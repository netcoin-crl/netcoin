# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in Python. It is built for learning how wallets, transactions, blocks, mining, mempools, nodes, explorers, payments, and app-layer tools fit together.

NetCoin is **not Bitcoin**, does not connect to the Bitcoin network, and should not be used as real money software. Public testnet NET has no real-money value.

> Current release: **v0.7.2**

## Public Testnet Apps

Use the hosted public testnet apps here:

| App | Purpose |
| --- | --- |
| Wallet | <https://wallet.netcoin.online> |
| Explorer | <https://explorer.netcoin.online> |
| Pay | <https://pay.netcoin.online> |
| Merchant | <https://merchant.netcoin.online> |
| Faucet | <https://faucet.netcoin.online> |
| Community | <https://community.netcoin.online> |
| Markets | <https://markets.netcoin.online> |
| Docs | <https://docs.netcoin.online> |
| API Docs | <https://api.netcoin.online> |
| Status | <https://status.netcoin.online> |

The public sites are separated by purpose so the Explorer stays focused and users are not overwhelmed.

| Site | What belongs there |
| --- | --- |
| Wallet | Create or restore a wallet, receive, send, contacts, backups, wallet tools |
| Explorer | Chain lookup, latest blocks, latest transactions, network health summary |
| Pay | Customer checkout, payment requests, invoices, receipts |
| Merchant | Business dashboard, POS, invoices, refunds, API keys, webhooks, exports, agreements |
| Faucet | Testnet coin requests and faucet status |
| Community | Community links, campaigns, bounties, gifts, leaderboards |
| Markets | Phase 7 prediction-market demos and market experiments |
| Docs | User, wallet, merchant, node, and developer guides |
| API Docs | Endpoint reference, examples, auth notes, webhook references |
| Status | Public health and availability checks |

## Safety Notice

NetCoin is a testnet and learning project.

- Testnet NET has no real-money value.
- Do not store real funds in NetCoin wallets.
- Do not share seed phrases, private keys, wallet files, API keys, or tokens.
- Hosted tools are for public-testnet experimentation.
- Production use would require independent security review, legal review, audits, infrastructure hardening, and a real user ecosystem.

## Features

### Public app ecosystem

- Responsive layouts for mobile, tablet, laptop, and desktop.
- Independent websites for Wallet, Explorer, Pay, Merchant, Faucet, Community, Markets, Docs, API Docs, and Status.
- Shared navigation across the public NetCoin apps.
- Wallet site for wallet actions, contacts, backups/imports, wallet modes, and wallet tools.
- Explorer site focused on chain lookup, latest blocks, latest transactions, and network health.
- Pay site for simple checkout and customer-facing payment flows.
- Merchant site for invoices, POS, business profiles, API keys, webhooks, exports, refunds, agreements, and reports.
- Faucet site for requesting public-testnet coins.
- Community site for campaigns, bounties, gifts, social links, and leaderboards.
- Markets site for prediction-market demos and Phase 7 experiments.
- Docs and API Docs sites for public help and developer references.

### Core chain

- UTXO chain validation.
- Real proof-of-work mining.
- 2-minute target blocks with difficulty retargeting.
- Testnet lone-miner rule so the chain can keep moving.
- Merkle roots.
- Coinbase rewards and 100-block coinbase maturity.
- secp256k1 ECDSA signatures.
- BIP340-style Schnorr signatures for Taproot-like key-path spends.
- Legacy, P2SH-SegWit, SegWit-style, and Taproot-style addresses.
- Educational Script engine.
- P2PKH, P2SH, P2WPKH, P2WSH, and P2TR script templates.
- Multisig helpers.
- Timelock helpers.
- Transaction locktime and sequence handling.
- Opt-in RBF signaling.
- Mempool policy limits.
- Block weight limit.
- Raw Bitcoin-style transaction and block hex export.
- SegWit-style txid/wtxid split.

### Network and node tools

- HTTP node API.
- Experimental binary TCP P2P server/client.
- Headers-first sync shape.
- Compact-block summaries.
- BIP158-style compact block filters.
- Relay queue and peer inventory cache.
- Cumulative-work fork choice.
- Reorg, rollback, and mempool revalidation.
- Orphan block candidate handling.
- Public endpoint rate limiting.
- API-backed explorer and public status endpoints.

### Wallet and developer tools

- Encrypted wallet files.
- Deterministic NetCoin seed phrases.
- HD wallet derivation.
- Watch-only wallet files.
- Descriptor helpers.
- PSBT-like signing flow.
- Browser wallet and local web wallet.
- Saved contacts shared between wallet and explorer tools.
- Payment URI support.
- QR/payment-link support in browser tools.
- Backup/import/export flows for wallet-related data.
- Signed messages.
- JSON-RPC server.
- Mining-pool template server.
- Faucet hardening support.
- Local multi-node soak/stress harness.
- Deterministic fuzz smoke runner.
- Reindex and crash-safe JSON persistence.
- Optional SQLite backend.
- Pruned mode.

## Use the Hosted Wallet

Open the hosted wallet:

```text
https://wallet.netcoin.online
```

Create a new wallet or restore an existing one. Back up your recovery phrase before using the wallet. The browser wallet should be used over HTTPS.

## Get Testnet Coins

Open the faucet:

```text
https://faucet.netcoin.online
```

Paste a NetCoin testnet address from your wallet and request coins. Faucet limits may apply.

## Explore the Chain

Open the explorer:

```text
https://explorer.netcoin.online
```

Use it to look up blocks, transactions, addresses, and public network health.

## Use Merchant and Pay Tools

Customer checkout lives in Pay:

```text
https://pay.netcoin.online
```

Business tools live in Merchant:

```text
https://merchant.netcoin.online
```

Merchant features are separated from the Explorer so normal chain lookup remains simple.

## API Docs

Developer endpoint documentation lives here:

```text
https://api.netcoin.online
```

Use the API Docs site for public endpoint examples, webhook references, and integration notes.

## Install Locally From Source

Install locally only if you want to inspect the code, run tests, mine on testnet, or run your own node.

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

After opening a new terminal later, activate the virtual environment again instead of recreating it.

macOS / Linux:

```bash
cd netcoin
source .venv/bin/activate
```

Windows PowerShell:

```powershell
cd netcoin
.\.venv\Scripts\Activate.ps1
```

## Public Testnet Nodes

Use the public seed hostnames when a command asks for a node URL:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

Quick health check:

macOS / Linux:

```bash
curl http://seed1.netcoin.online:28444/info
curl http://seed2.netcoin.online:28444/health
curl "http://seed3.netcoin.online:28444/latest?n=5"
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://seed1.netcoin.online:28444/info
Invoke-RestMethod http://seed2.netcoin.online:28444/health
Invoke-RestMethod "http://seed3.netcoin.online:28444/latest?n=5"
```

## Create a Local Wallet

```bash
python -m netcoin wallet-new --out miner.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet miner.json
```

Write down the recovery phrase. The wallet file controls your testnet coins.

## Mine on the Public Testnet

Mine one block:

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet miner.json --blocks 1
```

Mine continuously until you stop it with `Ctrl+C`:

macOS / Linux:

```bash
while true; do
  python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet miner.json --blocks 1
done
```

Windows PowerShell:

```powershell
while ($true) {
  python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet miner.json --blocks 1
}
```

Mining rewards are coinbase rewards. They show as `immature` until 100 more blocks are mined after them.

## Check Balance

Check your wallet:

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet miner.json
```

Check any address:

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --address <NETCOIN_ADDRESS>
```

Show wallet addresses:

```bash
python -m netcoin wallet-info --wallet miner.json
```

## Run a Local Browser Wallet

The hosted wallet is usually easier. For local testing, run:

```bash
python -m netcoin web --node http://seed1.netcoin.online:28444
```

Open:

```text
http://127.0.0.1:8088/
```

The local browser wallet runs on your computer and sends signed transactions to the selected public node.

## Run Your Own Testnet Node

Terminal 1: start a node and leave it running:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://seed1.netcoin.online:28444 --peer http://seed2.netcoin.online:28444 --peer http://seed3.netcoin.online:28444
```

Terminal 2: check it:

macOS / Linux:

```bash
curl http://127.0.0.1:28444/info
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:28444/info
```

Mine through your own local node:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json --blocks 1
```

## Project Status

Implemented code is useful for education, local experimentation, public-testnet demos, and integration prototypes. It is not a substitute for a real production cryptocurrency network.

Still not something code alone can create:

- Real global hashpower.
- A worldwide independent node network.
- Exchange listings.
- Real liquidity.
- Hardware wallet vendor support.
- A production security review.
- A public user ecosystem.

Those require people, infrastructure, review, miners, users, and time.
