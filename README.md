# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in Python. It is built for learning how wallets, transactions, blocks, mining, mempools, nodes, explorers, payments, and app-layer tools fit together.

NetCoin is **not Bitcoin**, does not connect to the Bitcoin network, and should not be used as real money software. Public-testnet NET has no real-money value.

> Current release: **v0.10.1** · 3 public seeds · deterministic emission (50 NET −10% / 265k blocks) · 5-minute blocks from height 5,010 · app-layer tokens + developer API keys

## Start here

| File | Purpose |
| --- | --- |
| [INSTRUCTIONS.md](INSTRUCTIONS.md) | Pick your system, then follow a complete beginner guide — [macOS](docs/INSTRUCTIONS_MAC.md), [Windows](docs/INSTRUCTIONS_WINDOWS.md), or [Linux](docs/INSTRUCTIONS_LINUX.md): install, make a wallet, mine test coins, check your balance, and open a wallet in your browser. |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards for participation. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute improvements. |
| [docs/RUN_YOUR_OWN.md](docs/RUN_YOUR_OWN.md) | Run everything yourself — mine to an address you already have, run your own node and public seed, and use NetCoin fully locally with no reliance on the public websites. |
| [ROADMAP.md](ROADMAP.md) | The plan: how NetCoin grows into simple money + a builder platform + strong infrastructure, layered so the base chain stays simple and secure. Every proposed feature, phased and risk-tagged. |
| [SECURITY.md](SECURITY.md) | How to report security issues. |
| [docs/PUBLIC_SITE_MAP.md](docs/PUBLIC_SITE_MAP.md) | Public site purpose map for Wallet, Explorer, Pay, Merchant, Community, Nodes, Security, Governance, Treasury, Docs, and API. |

## 5-minute quickstart (join the public testnet)

```bash
git clone https://github.com/netcoin-crl/netcoin.git && cd netcoin
python3 -m venv .venv && source .venv/bin/activate      # Windows: py -3 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e .

# 1) Create a wallet (WRITE DOWN the recovery phrase it prints)
python -m netcoin wallet-new --out my-wallet.json --mnemonic

# 2) Get free test coins: paste your net1... address at https://faucet.netcoin.online
#    (or use the raw-IP faucet http://18.220.89.128/faucet if your ISP blocks the domain)
#    You can claim once per hour.

# 3) Mine a block yourself (optional, ~minutes on a laptop; rewards unlock after 100 blocks)
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after

# 4) Check your balance
python -m netcoin balance --node http://18.220.89.128/api --wallet my-wallet.json
```

Prefer a browser? Use the hosted non-custodial wallet at <https://wallet.netcoin.online> — keys never leave your browser, and the Mining tab gives you a personal copy-paste mining command.

### Or run a node with Docker

```bash
docker compose up --build node        # joins the public testnet, API on http://127.0.0.1:28444
```

## Developer quickstart

```bash
# All app-layer writes on the hosted relay need a free developer key (NIP-0004):
curl -s -X POST https://api.netcoin.online/api/keys/register -H 'Content-Type: application/json' -d '{"app":"my-app"}'
# -> {"api_key":"nck_..."}  Send it as the X-Netcoin-Api-Key header on writes. Reads are open.
```

- **API reference:** [docs/openapi.yaml](docs/openapi.yaml) (served at <https://api.netcoin.online/openapi.yaml>)
- **SDKs:** [sdk/netcoin-python](sdk/netcoin-python/) · [sdk/netcoin-js](sdk/netcoin-js/)
- **Starter apps:** [examples/](examples/) (store checkout, loyalty tokens) · tip bots in [bots/](bots/)
- **App-layer NET-20 tokens:** create/mint/transfer via `/api/tokens` — indexed ledger, not consensus ([NIP-0004](docs/nips/NIP-0004.md) explains the auth model and its limits)
- **Improvement process:** [docs/nips/NIP-0001.md](docs/nips/NIP-0001.md) · upgrade activations: [docs/nips/NIP-0005.md](docs/nips/NIP-0005.md)

## Key network facts

| Parameter | Value |
| --- | --- |
| Block time | 2 min → **5 min from height 5,010** (activation-gated, no chain reset) |
| Block reward | 50 NET, −10% every 265,000 blocks (~132.5M NET max supply) |
| Reward maturity | 100 blocks |
| Difficulty retarget | every 30 blocks (+ lone-miner floor rule so the chain never stalls) |
| Faucet | 5 NET, once per hour |
| Node API port | 28444 (HTTP JSON) |
| Write auth | free self-service developer keys (`POST /api/keys/register`) |

## Sending large amounts (and the `consolidate` command)

Mining pays 50 NET per block, so a big balance is really hundreds of small
coins. A single send may use at most **120 inputs / 180k weight** (protects
public nodes), so very large sends can fail with *"too many inputs"*. The fix
is one command — sweep your small coins into one, then send normally:

```bash
python -m netcoin consolidate --node http://18.220.89.128/api --wallet my-wallet.json
```

Run it again after a confirmation if you have thousands of coins. In the
hosted browser wallet, sending **Max to your own address** does the same thing.

**Address types:** new wallets default to **SegWit** (`net1q…`) everywhere —
lowest fees, best support. **Taproot** (`net1p…`) is available in the CLI and
the hosted wallet (Address type selector). Legacy and P2SH-SegWit remain
spendable for existing coins but are no longer defaults.

## Public Testnet Apps

Use the hosted public-testnet apps here:

| App | Link | Purpose |
| --- | --- | --- |
| Wallet | <https://wallet.netcoin.online> | Create, restore, import private keys, receive, send, contacts, backups, and wallet tools. |
| Explorer | <https://explorer.netcoin.online> | Chain lookup, latest blocks, latest transactions, and network health. |
| Pay | <https://pay.netcoin.online> | Customer checkout, payment requests, invoices, and receipts. |
| Merchant | <https://merchant.netcoin.online> | Business dashboard, POS, invoices, refunds, API keys, webhooks, exports, agreements, and reports. |
| Faucet | <https://faucet.netcoin.online> | Request public-testnet NET. |
| Community | <https://community.netcoin.online> | Public discussion, improvement ideas, campaigns, bounties, gifts, and leaderboards. |
| Governance | <https://governance.netcoin.online> | Proposal board and community voting for improvement ideas. |
| Treasury | <https://treasury.netcoin.online> | Read-only transparency page for project-fund records if a treasury exists. |
| Markets | <https://markets.netcoin.online> | Phase 7 prediction-market demos and market experiments. |
| Nodes | <https://nodes.netcoin.online> | Node, public seed, peer, and decentralization dashboard. |
| Status | <https://status.netcoin.online> | Public service health and availability checks. |
| Security | <https://security.netcoin.online> | Security trust center, wallet safety, disclosure, and release-trust notes. |
| Learn | <https://learn.netcoin.online> | Beginner-friendly explanations of wallets, nodes, seeds, mining, and payments. |
| Download | <https://download.netcoin.online> | Install and run commands for macOS, Windows, and Linux. |
| Docs | <https://docs.netcoin.online> | User, wallet, merchant, node, and developer guides. |
| API Docs | <https://api.netcoin.online> | Public endpoint reference, examples, auth notes, and webhook references. |

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
python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online
```

Then open:

```text
http://127.0.0.1:8088/
```

Keep the local wallet bound to `127.0.0.1`. Do not expose it publicly. If it says **cannot reach the node**, first try `http://18.220.89.128/api`. If your network allows the domain normally, `https://api.netcoin.online/api` also works.


## Public API node for local tools

Use this public API node when a command asks for `--node` and you want the local wallet or miner to connect to the live public testnet without opening a custom seed port:

```text
http://18.220.89.128/api
```

Preferred public domain when your network allows it:

```text
https://api.netcoin.online/api
```

Some home networks or router security products can block `api.netcoin.online` or custom ports such as `28444`. If `curl https://api.netcoin.online/api/latest` fails, use the direct-IP API proxy above.

Create a wallet, mine one public-testnet block, and run the local browser wallet:

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after
python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online
```

Then open:

```text
http://127.0.0.1:8088/
```

## Public seed nodes

Use these node URLs when a command asks for a public node:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

Example: mine one public-testnet block after creating a wallet:

```bash
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after
```

Direct seed ports are still available for node operators, but the API proxy above is easier for local wallets and miners on home networks.


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

- Responsive desktop layouts with denser dashboard cards and mobile-friendly stacking.


### Public app ecosystem

- Responsive layouts for mobile, tablet, laptop, and desktop.
- Independent websites for Wallet, Explorer, Pay, Merchant, Faucet, Community, Governance, Treasury, Markets, Nodes, Status, Security, Learn, Download, Docs, and API Docs.
- Shared navigation across the public NetCoin apps.
- Wallet site for wallet actions, private-key import, session unlock, contacts, backups/imports, wallet modes, and wallet tools.
- Explorer site focused on chain lookup, latest blocks, latest transactions, and network health.
- Pay site for simple checkout and customer-facing payment flows.
- Merchant site for invoices, POS checkout, API keys, webhooks, refunds, agreements, CSV exports, and reports.
- Faucet site for requesting public-testnet coins.
- Community site for public discussion, improvement ideas, campaigns, bounties, gifts, social links, and leaderboards.
- Markets site for prediction-market demos and Phase 7 experiments.
- Nodes, Security, Learn, Download, Docs, and API Docs sites for public network visibility, safety, education, setup, and developer references.


### Wallet usability upgrades

- Private-key wallet import for users who already have a single NetCoin key.
- Encrypted private-key profiles stored locally in the browser.
- Session unlock so returning to the wallet in the same browser tab does not require signing in again until the tab is closed or the wallet is locked.
- Local wallet/miner instructions use `http://18.220.89.128/api` as the current no-tunnel fallback, with `https://api.netcoin.online/api` as the preferred domain when the user network allows it.

### Core chain

- UTXO chain validation.
- Real proof-of-work mining.
- 2-minute target blocks with difficulty retargeting.
- Testnet lone-miner rule so the chain can keep moving.
- Merkle roots.
- Coinbase rewards and 100-block coinbase maturity.
- Reward schedule: starts at 50 NET and decreases 10% every 265,000 blocks
  (`subsidy = 50 NET × (9/10)^floor(height / 265,000)`), for a long-run supply of
  ~132.5M NET. See [docs/ECONOMICS_PLAN.md](docs/ECONOMICS_PLAN.md).
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


### Recent UI updates

- Local browser wallet now defaults to the HTTPS public API proxy to avoid home-network blocks on custom ports.
- Merchant site now has a clearer invoice/POS workflow, API/webhook tools, refund planning, agreements, exports, and invoice table.
- Community site now includes a public discussion board, improvement ideas, bounties, and leaderboards backed by app-layer endpoints.

## Professional ecosystem additions

The public NetCoin site set now includes focused tools for a more professional cryptocurrency testnet:

- **Nodes** — public seed/node health and instructions for becoming a seed.
- **Status** — service and network health checks.
- **Security** — trust center, wallet safety, responsible disclosure, and pre-mainnet checklist.
- **Download** — public install/run instructions for macOS, Windows, and Linux.
- **Governance** — NetCoin Improvement Proposal style idea board.
- **Treasury** — read-only transparency page for any configured project addresses.
- **Learn** — beginner education for wallets, nodes, seeds, transactions, and mining.

The wallet also supports importing a single private key as an encrypted profile and keeps the wallet unlocked only for the current browser tab/session, so switching between NetCoin sites does not force repeated unlocks.



## NetCoin ecosystem structure

NetCoin uses a mode-based public ecosystem so new users are not overwhelmed and advanced users can still find deeper tools.

- **Simple mode:** Wallet, Pay, Explorer, Faucet, Learn, and Community basics.
- **Merchant mode:** Merchant dashboard, invoices, POS, reports, API keys, and webhooks.
- **Developer mode:** API docs, SDK examples, explorer APIs, downloads, and release verification.
- **Node Operator mode:** Network health, public seeds, status, mining, and public-seed guides.
- **Community mode:** Discussion, ideas, bounties, governance, roadmap, and treasury transparency.
- **Advanced / Labs mode:** Experimental markets, polls, and contract-template demos.

The public navigation is intentionally grouped: Learn includes Download, Governance includes Treasury, Nodes/Status live under Network, API docs live under the developer hub, and Markets are labeled as Labs/demo features.

## Professional/security roadmap now included

The site package includes a Trust Center, Network hub, Developer hub, release-verification guidance, wallet setup wizard, merchant onboarding checklist, community reports, anti-secret public-post filtering, API rate limiting, and broader desktop layouts.


## NetCoin public site map

NetCoin now uses a mode-aware public ecosystem so new users see a simple path and curious users can explore deeper tools without every page becoming crowded.

- **Wallet** — create, restore, import private keys, send, receive, contacts, and session unlock.
- **Pay** — customer checkout, payment requests, QR/payment links, and receipts.
- **Explorer** — chain lookup only: blocks, transactions, addresses, fees, mempool summary, and network snapshot.
- **Merchant** — invoices, POS checkout, refunds, reports, API keys, webhooks, recurring payments, and escrow-style business workflows.
- **Community** — discussion, improvement ideas, bounties, roadmap participation, and safety guidelines.
- **Learn** — beginner education plus download/install/run instructions for macOS, Windows, and Linux.
- **Network** — nodes, public seeds, status, mining, uptime, versions, and seed-operator guidance.
- **Developers** — API docs, SDKs, webhook examples, local development, and integration notes.
- **Governance** — NetCoin Improvement Proposals, voting, roadmap, and treasury transparency.
- **Security** — trust center, wallet safety, release verification, disclosure policy, and hardening roadmap.
- **Labs** — isolated testnet experiments such as prediction-market demos and Phase 7 features.

Use the site-wide **Mode** selector to switch between Simple, Merchant, Developer, Node Operator, Community, and Labs views.

### Reliability and public-node protections

NetCoin includes public-node safeguards so wallet, explorer, mining, and seed traffic do not overload the same node:

- Wallet send pre-checks for spendable balance, input count, and transaction weight.
- Clear timeout/error messages when a send is too large or the node is busy.
- Mempool expiry, mempool info, and operator mempool-clear tools.
- Fast `/health` and `/status-lite` node endpoints.
- Cached `/latest` and `/info` reads for explorer/status pages.
- Address-history pagination for explorer/API use.

See [`docs/NODE_RELIABILITY_AND_LOAD.md`](docs/NODE_RELIABILITY_AND_LOAD.md).
