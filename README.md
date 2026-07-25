# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in Python. It is built for learning how wallets, transactions, blocks, mining, mempools, nodes, explorers, payments, and app-layer tools fit together.

NetCoin is **not Bitcoin**, does not connect to the Bitcoin network, and should not be used as real money software. Public-testnet NET has no real-money value.

> Current release: **v0.42.0** · website UI clarity pass, strict proof tooling, Rust/TS/Python parity, explicit mainnet evidence gates, an Admin/Simple site view toggle, and real (non-preview) order/dispute actions in the Markets UI.

## Start here

| File | Purpose |
| --- | --- |
| [INSTRUCTIONS.md](INSTRUCTIONS.md) | Pick your system, then follow a complete beginner guide — [macOS](docs/INSTRUCTIONS_MAC.md), [Windows](docs/INSTRUCTIONS_WINDOWS.md), or [Linux](docs/INSTRUCTIONS_LINUX.md): install, make a wallet, mine test coins, check your balance, and open a wallet in your browser. |
| [docs/NODES.md](docs/NODES.md) | Everything node-related in one place: install, run, sync, mine, become a public seed, troubleshoot. |
| [docs/RUN_YOUR_OWN.md](docs/RUN_YOUR_OWN.md) | Run everything yourself with no reliance on the public websites. |
| [ROADMAP.md](ROADMAP.md) | The plan: how NetCoin grows into simple money + a builder platform + strong infrastructure, phased and risk-tagged. |
| [SECURITY.md](SECURITY.md) | How to report security issues. |
| [docs/WHY_NETCOIN.md](docs/WHY_NETCOIN.md) | Why this project exists, who it's for, and what's real vs. testnet convenience. |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) / [CONTRIBUTING.md](CONTRIBUTING.md) | Community standards and how to contribute. |
| [docs/PUBLIC_SITE_MAP.md](docs/PUBLIC_SITE_MAP.md) | Purpose of each public site (Wallet, Explorer, Pay, Merchant, Community, Nodes, Security, Governance, Treasury, Docs, API). |
| [docs/EXCHANGE_INTEGRATION.md](docs/EXCHANGE_INTEGRATION.md) | Sandbox exchange integration: private RPC, deposits, withdrawals, confirmations, reorg handling. |

## 5-minute quickstart (join the public testnet)

```bash
git clone https://github.com/netcoin-crl/netcoin.git && cd netcoin
python3 -m venv .venv && source .venv/bin/activate      # Windows: py -3 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e .

# 1) Create a wallet (WRITE DOWN the recovery phrase it prints)
python -m netcoin wallet-new --out my-wallet.json --mnemonic

# 2) Get free test coins: paste your net1... address at https://faucet.netcoin.online
#    (or the raw-IP faucet http://18.220.89.128/faucet if your ISP blocks the domain)
#    You can claim once per hour.

# 3) Mine a block yourself (optional; rewards unlock after 100 blocks)
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after

# 4) Check your balance
python -m netcoin balance --node http://18.220.89.128/api --wallet my-wallet.json
```

Prefer a browser? Use the hosted non-custodial wallet at <https://wallet.netcoin.online> — keys never leave your browser, and the Mining tab gives you a copy-paste mining command.

```bash
docker compose up --build node        # or run a node with Docker; joins the public testnet, API on http://127.0.0.1:28444
```

**Running your own node, syncing, or becoming a public seed?** See [docs/NODES.md](docs/NODES.md) — it covers all of this in one place, including troubleshooting.

## Developer quickstart

```bash
# All app-layer writes on the hosted relay need a free developer key (NIP-0004):
curl -s -X POST https://api.netcoin.online/api/keys/register -H 'Content-Type: application/json' -d '{"app":"my-app"}'
# -> {"api_key":"nck_..."}  Send it as the X-Netcoin-Api-Key header on writes. Reads are open.
```

- **API reference:** [docs/openapi.yaml](docs/openapi.yaml) (served at <https://api.netcoin.online/openapi.yaml>)
- **SDKs:** [sdk/netcoin-python](sdk/netcoin-python/) · [sdk/netcoin-js](sdk/netcoin-js/) · [sdk/netcoin-developer](sdk/netcoin-developer/)
- **Starter apps:** [examples/](examples/) (store checkout, loyalty tokens) · tip bots in [bots/](bots/)
- **App-layer NET-20 tokens:** create/mint/transfer via `/api/tokens` — indexed ledger, not consensus ([NIP-0004](docs/nips/NIP-0004.md) explains the auth model and its limits)
- **Exchange sandbox integration:** [docs/EXCHANGE_INTEGRATION.md](docs/EXCHANGE_INTEGRATION.md) — private RPC, deposit watching, withdrawals, confirmation policy, reorg handling. Not a real-money listing claim.
- **Improvement process:** [docs/nips/NIP-0001.md](docs/nips/NIP-0001.md) · upgrade activations: [docs/nips/NIP-0005.md](docs/nips/NIP-0005.md)

## Key network facts

| Parameter | Value |
| --- | --- |
| Block time | 2 min → **5 min from height 5,010** (activation-gated, no chain reset) |
| Block reward | 50 NET, −10% every 265,000 blocks (~132.5M NET max supply) — see [docs/ECONOMICS_PLAN.md](docs/ECONOMICS_PLAN.md) |
| Reward maturity | 100 blocks |
| Difficulty retarget | every 30 blocks (+ lone-miner floor rule so the chain never stalls) |
| Faucet | 5 NET, once per hour |
| Node API port | 28444 (HTTP JSON) — full port/protocol table in [docs/NODES.md](docs/NODES.md#quick-facts) |
| Write auth | free self-service developer keys (`POST /api/keys/register`) |

## Sending large amounts

Mining pays 50 NET per block, so a big balance is really hundreds of small
coins. Every send uses **consolidating coin selection** (sweeps in extra small
coins up to the per-transaction limit, up to **200 inputs**), so normal
spending steadily shrinks your coin count instead of fragmenting it.

If a send is still larger than one transaction can hold, the wallet tells you
exactly how much you can send now and points you to consolidation:

```bash
python -m netcoin consolidate --node http://18.220.89.128/api --wallet my-wallet.json
```

In the hosted browser wallet, sending **Max to your own address** does the same.

**Running a public node?** Install the optional fast-verification accelerator
so large transactions validate instantly:

```bash
pip install "netcoin[fast]"
NETCOIN_FAST_CRYPTO=1 python -m netcoin node --host 0.0.0.0 --seeds
```

It changes verification *speed* only, never which signatures are valid
(proven by a differential fuzz test). Python 3.13 is the recommended runtime
for public Linux seeds today.

**Address types:** new wallets default to **SegWit** (`net1q…`) — lowest fees,
best support. **Taproot** (`net1p…`) is available in the CLI and hosted
wallet. Legacy and P2SH-SegWit remain spendable for existing coins but are no
longer defaults.

## Public testnet apps

| App | Link | Purpose |
| --- | --- | --- |
| Start | <https://netcoin.online> | Beginner hub: wallet/pay/community basics, download, faucet, explorer, safety links. |
| Wallet | <https://wallet.netcoin.online> | Create, restore, import keys, receive, send, contacts, backups. |
| Explorer | <https://explorer.netcoin.online> | Chain lookup, latest blocks/transactions, network health. |
| Pay | <https://pay.netcoin.online> | Focused checkout, payment requests, invoices, receipts. |
| Merchant | <https://merchant.netcoin.online> | Business dashboard, POS, invoices, refunds, API keys, webhooks, exports. |
| Faucet | <https://faucet.netcoin.online> | Request public-testnet NET. |
| Community | <https://community.netcoin.online> | Discussion, improvement ideas, campaigns, bounties, leaderboards. |
| Governance | <https://governance.netcoin.online> | Proposal board and community voting. |
| Treasury | <https://governance.netcoin.online#treasury> | Read-only transparency page for project-fund records. |
| Markets | <https://markets.netcoin.online> | Prediction-market demos and market experiments. |
| Nodes | <https://nodes.netcoin.online> | Node, public seed, peer, and decentralization dashboard. |
| Status | <https://status.netcoin.online> | Public service health and availability checks. |
| Security | <https://security.netcoin.online> | Trust center, wallet safety, disclosure, release-trust notes. |
| Learn | <https://learn.netcoin.online> | Beginner explanations of wallets, nodes, seeds, mining, payments. |
| Download | <https://download.netcoin.online> | Install and run commands for macOS, Windows, Linux. |
| Docs | <https://docs.netcoin.online> | Doc map: M1 tester path, feedback intake, pilot plan. |
| API Docs | <https://api.netcoin.online> | Endpoint reference, examples, auth notes, webhook references. |

Every site uses the shared NetCoin shell for navigation, safety text, and
responsive UI. Source folders live in [sites/](sites/); after changing shared
shell assets run `make site-sync`, and `make site-audit` before deployment.
Full per-site purpose breakdown: [docs/PUBLIC_SITE_MAP.md](docs/PUBLIC_SITE_MAP.md).

## Safety notice

NetCoin is a testnet and learning project.

- Testnet NET has no real-money value.
- Do not store real funds in NetCoin wallets.
- Do not share seed phrases, private keys, wallet files, API keys, or tokens.
- Hosted tools are for public-testnet experimentation.
- Production use would require independent security review, legal review, audits, infrastructure hardening, and a real user ecosystem.

## Feature overview

**Core chain:** UTXO validation, real proof-of-work mining, 2-minute target
blocks with difficulty retargeting (lone-miner floor rule), merkle roots,
coinbase rewards with 100-block maturity, secp256k1 ECDSA + BIP340-style
Schnorr signatures, Legacy/P2SH-SegWit/SegWit/Taproot-style addresses,
educational Script engine (P2PKH/P2SH/P2WPKH/P2WSH/P2TR templates, multisig
and timelock helpers), locktime/sequence handling, opt-in RBF, mempool policy
and block weight limits.

**Network and node tools:** HTTP node API, experimental binary TCP P2P,
headers-first sync, compact-block summaries, BIP158-style compact filters,
cumulative-work fork choice, reorg/rollback/mempool revalidation, orphan
block handling, public endpoint rate limiting. See [docs/NODES.md](docs/NODES.md)
for running one.

**Wallet and developer tools:** encrypted wallet files, deterministic seed
phrases, HD derivation, watch-only wallets, descriptor helpers, PSBT-based
signing (including M-of-N multisig spends), hosted + local browser wallets,
saved contacts, payment URIs/QR support, signed messages, JSON-RPC server,
mining-pool template server, local multi-node soak/stress harness, SQLite or
pruned-mode storage.

## Project status

Implemented code is useful for education, local experimentation,
public-testnet demos, and integration prototypes. It is not a substitute for
a real production cryptocurrency network. Still not something code alone can
create: real global hashpower, a worldwide independent node network,
exchange listings, liquidity, merchant adoption, regulatory clarity,
real-money value, trust. See [docs/REAL_VALUE_EXCHANGE_PLAN.md](docs/REAL_VALUE_EXCHANGE_PLAN.md)
for what that would actually take.

## License

Copyright © 2026 NetCoin. Licensed under the **GNU Affero General Public
License v3.0 or later (AGPL-3.0-or-later)** — see [LICENSE](LICENSE).

You are free to use, study, run, and modify NetCoin, but any distributed or
network-hosted derivative must remain open source under the same license and
must preserve attribution. You may **not** take this code, close it, rebrand
it, and pass it off as your own proprietary product.
