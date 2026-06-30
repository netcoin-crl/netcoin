# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in Python. It is built for learning how wallets, transactions, blocks, mining, mempools, nodes, explorers, payments, and app-layer tools fit together.

NetCoin is **not Bitcoin**, does not connect to the Bitcoin network, and should not be used as real money software. Public-testnet NET has no real-money value.

> Current release: **v0.7.2**

## Start here

| File | Purpose |
| --- | --- |
| [INSTRUCTIONS.md](INSTRUCTIONS.md) | Beginner-friendly setup for macOS, Windows, and Linux, including public seed nodes, wallet creation, mining, balance checks, running a local node, running the local browser wallet, and becoming a public seed. |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards for participation. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute improvements. |
| [SECURITY.md](SECURITY.md) | How to report security issues. |

## Public Testnet Apps

Use the hosted public-testnet apps here:

| App | Link | Purpose |
| --- | --- | --- |
| Wallet | <https://wallet.netcoin.online> | Create or restore a wallet, receive, send, contacts, backups, and wallet tools. |
| Explorer | <https://explorer.netcoin.online> | Chain lookup, latest blocks, latest transactions, and network health. |
| Pay | <https://pay.netcoin.online> | Customer checkout, payment requests, invoices, and receipts. |
| Merchant | <https://merchant.netcoin.online> | Business dashboard, POS, invoices, refunds, API keys, webhooks, exports, agreements, and reports. |
| Faucet | <https://faucet.netcoin.online> | Request public-testnet NET. |
| Community | <https://community.netcoin.online> | Campaigns, bounties, gifts, leaderboards, and public links. |
| Markets | <https://markets.netcoin.online> | Phase 7 prediction-market demos and market experiments. |
| Docs | <https://docs.netcoin.online> | User, wallet, merchant, node, and developer guides. |
| API Docs | <https://api.netcoin.online> | Public endpoint reference, examples, auth notes, and webhook references. |
| Status | <https://status.netcoin.online> | Public health and availability checks. |

The public sites are separated by purpose so the Explorer stays focused and users are not overwhelmed.

## Quick install from source

For exact beginner steps, use [INSTRUCTIONS.md](INSTRUCTIONS.md).

macOS / Linux:

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```

Windows PowerShell:

```powershell
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```


## Local browser wallet quick start

After installing from source, you can run a local browser wallet on your own computer:

```bash
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Then open:

```text
http://127.0.0.1:8088/
```

Keep the local wallet bound to `127.0.0.1`. Do not expose it publicly.

## Public seed nodes

Use these node URLs when a command asks for a public node:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

Example: mine one public-testnet block after creating a wallet:

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```


## Become a public seed

A public seed is a NetCoin node that other users can connect to. The beginner guide includes copy/paste steps for macOS, Windows, and Linux, including how to find your IP, open the right ports, start the node, advertise your seed URL, and mine through your own seed.

Start here: [INSTRUCTIONS.md#become-a-public-seed](INSTRUCTIONS.md#become-a-public-seed).

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
- Public seed instructions for macOS, Windows, Linux, home-router setups, and VPS/cloud setups.

### Wallet and developer tools

- Encrypted wallet files.
- Deterministic NetCoin seed phrases.
- HD wallet derivation.
- Watch-only wallet files.
- Descriptor helpers.
- PSBT-like signing flow.
- Hosted browser wallet and updated local browser wallet.
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

## Project Status

Implemented code is useful for education, local experimentation, public-testnet demos, and integration prototypes. It is not a substitute for a real production cryptocurrency network.

Still not something code alone can create:

- Real global hashpower.
- A worldwide independent node network.
- Exchange listings.
- Liquidity.
- Merchant adoption.
- Regulatory clarity.
- Real-money value.
- Trust.

## License

MIT. See [LICENSE](LICENSE).
