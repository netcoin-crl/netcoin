# NetCoin Docs

NetCoin is an educational, Bitcoin-like public-testnet project. These docs explain how to use the wallet, explorer, faucet, merchant tools, public API, and local developer commands.

NetCoin is **not Bitcoin** and public-testnet NET has no real-money value.

## Public apps

| App | Link | Purpose |
| --- | --- | --- |
| Wallet | <https://wallet.netcoin.online> | Create, restore, import private keys, send, receive, contacts, backups |
| Explorer | <https://explorer.netcoin.online> | Blocks, transactions, addresses, and network health |
| Pay | <https://pay.netcoin.online> | Customer checkout and payment requests |
| Merchant | <https://merchant.netcoin.online> | Invoices, POS, API keys, webhooks, exports, reports |
| Faucet | <https://faucet.netcoin.online> | Request public-testnet NET |
| Community | <https://community.netcoin.online> | Discussion, ideas, bounties, gifts, leaderboards, links |
| Governance | <https://governance.netcoin.online> | Improvement proposals and votes |
| Treasury | <https://treasury.netcoin.online> | Transparent fund records if a treasury exists |
| Markets | <https://markets.netcoin.online> | Prediction-market demos and Phase 7 experiments |
| Nodes | <https://nodes.netcoin.online> | Public seeds, peers, and network participation |
| Status | <https://status.netcoin.online> | Public service health |
| Security | <https://security.netcoin.online> | Trust center and safety notes |
| Learn | <https://learn.netcoin.online> | Beginner concepts |
| Download | <https://download.netcoin.online> | Install and run commands |
| API Docs | <https://api.netcoin.online> | Public endpoint reference, community posts, merchant integrations, and examples |

## Start here

- [Beginner instructions](../INSTRUCTIONS.md)
- [Run the local browser wallet](../INSTRUCTIONS.md#run-the-local-netcoin-wallet)
- [Become a public seed](../INSTRUCTIONS.md#become-a-public-seed)
- [User guide](USER_GUIDE.md)
- [Starter kit](STARTER_KIT.md)
- [Testnet guide](TESTNET.md)
- [Wallet modes and site split](WALLET_MODES_AND_SITE_SPLIT.md)
- [Mining guide](MINING.md)
- [Node runner guide](NODE_RUNNER.md)
- [Public seed hosting guide](PUBLIC_SEED_HOSTING.md)
- [Public site map](PUBLIC_SITE_MAP.md)
- [API and architecture overview](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Limitations](LIMITATIONS.md)
- [Security policy](../SECURITY.md)

## Install from source

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

## Public testnet node URLs

Use these hostnames when a command asks for a public node URL:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

## Safety

Never share wallet files, seed phrases, private keys, API keys, or tokens. Public-testnet coins are for testing only and have no real-money value.


### Recent UI updates

- Private-key import and session unlock were added to the hosted wallet.
- New Nodes, Security, Learn, Download, and Governance sites were added for a more professional public ecosystem.

- Local browser wallet now defaults to the HTTPS public API proxy to avoid home-network blocks on custom ports.
- Merchant site now has a clearer invoice/POS workflow, integration cards, and invoice table.
- Community site now includes local discussion drafts and improvement ideas so testers can organize feedback before a hosted forum is connected.


## Site-wide modes

NetCoin sites now share a global mode selector: Simple, Merchant, Developer, Node Operator, Community, and Advanced/Labs. This keeps the public UI clean while preserving deeper tools for curious users. Learn includes download/install instructions, Governance includes Treasury transparency, Nodes/Status are grouped as Network, API docs live in the developer/API hub, and Markets are isolated as Labs.
