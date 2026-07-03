# NetCoin Roadmap

The goal: **a one-stop shop that isn't a jack-of-all-trades** — simple, reliable
money for everyone; powerful tools for builders; strong infrastructure for
operators — without the base chain becoming fragile or the wallet becoming
cluttered.

## The two rules that make that possible

1. **One excellent core, clearly-labeled optional rooms.** The base chain and the
   simple-money wallet must be *master-level* and stable. Everything else is an
   **opt-in module** (a "mode") that is allowed to start basic without hurting the
   core. A one-stop shop works when it has one great front door and clearly-marked
   back rooms — not a cluttered front door.
2. **The turn-it-off test.** If disabling a feature breaks simple Send / Receive /
   Balance, it is in the wrong layer. Tokens, contracts, privacy, channels — a
   normal user must never see them, and turning them off must change nothing for
   that user.

## Risk legend (this decides ordering as much as usefulness)

| | Layer | Meaning |
|---|---|---|
| 🟢 | **App / UI** | Frontend or app-layer service. No consensus change, no fork risk, no audit gate. **Build freely.** |
| 🟡 | **Wallet / infra** | Wallet-side crypto or node/ops tooling. No consensus change, but security-sensitive. |
| 🔴 | **Consensus / core crypto** | Changes block validation or ships new cryptography. Fork risk **and** needs a third-party audit. **Gate hard; mostly "research shelf".** |

> Current base: pure-Python educational testnet, unaudited crypto, one primary
> developer, 3 small public seeds, v0.7.8. That reality sets the risk bar: freeze
> the base chain, build on the app/wallet layers, and park the 🔴 items until
> there's an audit and more hands.

## Wallet modes (progressive disclosure — how "simple AND powerful" coexist)

Same wallet, different doors. Default is **Simple**. Nothing powerful is deleted,
just hidden behind a mode toggle.

- **Simple** — Home, Send, Receive, Activity, Contacts, Settings.
- **Merchant** — Invoices, Checkout, Refunds, Webhooks, Reports.
- **Developer** — API keys, Tokens, Contract templates, Testnet/sandbox tools.
- **Node Operator** — Peers, Mempool, Mining, Logs, Health.
- **Governance / Treasury** — Proposals, Voting, Bounties, Reports.

---

# Phases

Sequenced **foundation → core → platform → depth → research**, not by track. Each
phase is a release you can ship and be proud of before the next.

## Phase 0 — Trust foundation (v0.8) · *do this first*

Reliability and trust are the substrate everything else sits on, and most of this
is already ~80% built.

- 🟢 **Auth + API keys** on all app-layer write endpoints (invoices, webhooks,
  escrows, usernames are open today) — blocks everyone from safely building on them.
- 🟡 **Signed + reproducible releases**, checksums, published verification steps.
- 🟡 **Git-sourced, test-gated deploy** for seeds (stop editing code on servers).
- 🟢 **`nodes.netcoin.online` status dashboard** — seeds, heights, latency, mempool,
  version, faucet, indexer (uses existing `/health`, `/status-lite`, `/peers`).
- 🟢 **Security policy + bug-bounty page**, known-scam-address list, domain-verify notes.
- 🟢 **NIP-0001 improvement process** — the disciplined way changes get proposed,
  and the place to say "no / later" to everything on the research shelf.
- 🟡 **Monitoring/alerts** (Prometheus metrics + Discord/health alerts).
- 🔴 **Upgrade-activation standard** (write it down as a NIP; you already do
  height-gated activation — formalize it).

## Phase 1 — Simple-money core (v0.9) · *the "Cash App feel"*

All 🟢 frontend/UX on top of endpoints that already exist. This is where NetCoin
becomes usable as money for a normal person.

- 🟢 **Plain-English balances:** Available / Pending / Mining-rewards-locked +
  maturity countdown ("spendable in ~96 blocks"). Hide UTXO/mempool/coinbase words.
- 🟢 **Send preview** before broadcast (amount, fee, change, recipient).
- 🟢 **Fee selector** (slow / normal / fast) + auto fee estimation (`/fee-estimates`).
- 🟢 **Send-Max** with safe fee deduction; **large-send warning**; stuck-send reset UI.
- 🟢 **Address book / contacts** + human names (`@name`, merchant names).
- 🟢 **QR send/receive**, **payment links**, **payment requests**, **receipts**, tx notes.
- 🟢 **One-click wallet creation**, recovery-phrase backup checklist, **backup
  verification**, private-key import with warnings.
- 🟡 **Local unlock** (Face/Touch ID or OS keychain), wallet auto-lock, clipboard clearing.
- 🟢 **Address-reuse warnings** and **never-reuse-addresses by default** ← your
  privacy track's first and best feature belongs here (free, invisible, no downside).
- 🟢 **Mining page for normal users:** one-click local miner, rewards + maturity
  countdown, block-found notification, `netcoin mine --wallet …` (no node URL in simple mode).

## Phase 2 — Builder platform (v0.10) · *turn what exists into a product*

Mostly 🟢 — documenting and packaging endpoints you already have. Requires Phase 0
auth to be safe.

- 🟢 **OpenAPI spec** for the public API; hosted reference at `api.netcoin.online`.
- 🟢 **JavaScript SDK** and **Python SDK** (thin wrappers over existing endpoints).
- 🟢 **Merchant tools:** hosted invoice pages, payment button, checkout/POS mode,
  refunds, CSV/tax export, customer receipts, payment-expiry timer, partial/over/under-payment handling.
- 🟢 **Webhooks** (paid + confirmed), **API-key dashboard**, **rate-limit dashboard**.
- 🟢 **Faucet API**, **sandbox mode**, **Docker dev node**, `local dev node` command.
- 🟢 **Starter templates + example apps:** store, tip bot, bounty board, voting app,
  subscription app, game-reward system.
- 🟢 **Explorer API pagination**, indexer API; **WebSocket event stream** (new blocks/txs).
- 🟢 **Integrations:** Discord/Telegram payment bot; Shopify/WooCommerce plugin (later).

## Phase 3 — Depth per track (v0.11+) · *opt-in modules; base chain still frozen*

Now go deep — but each item lives in a mode and passes the turn-it-off test.

**Money depth**
- 🟡 Coin control (advanced mode), transaction batching, wallet labels.
- 🟡 HD wallets with many accounts, output descriptors, watch-only wallets, PSBT
  full workflow, air-gapped signing, recovery-phrase health check.
- 🟡 Multi-device wallet sync **without leaking keys** (encrypted sync).
- 🟢 Address-poisoning detection, suspicious-transaction warnings.
- 🔴 Replace-by-fee (RBF) and Child-pays-for-parent (CPFP) — mempool policy, small
  consensus/policy change; gate as a NIP.

**Builder depth**
- 🟢 **Contract *templates*** (safe, not a VM): 2-of-3 escrow, time-locked savings,
  refundable merchant payments, subscriptions-with-approval, treasury multisig,
  DAO spending approvals, inheritance/recovery wallet, simple condition/bet contracts.
- 🟢 **App-layer tokens** behind "Apps mode": NET-20 fungible, NET-721 collectibles,
  NET-1155 multi-asset, stablecoin support, loyalty points, coupons, game credits,
  DAO shares, community badges — as an **indexed ledger**, not a consensus change.
- 🟢 Token explorer, token balances in wallet, airdrop tool, mint/burn/freeze (app-layer).
- 🟢 GraphQL API, CLI app generator.
- 🟡 **Account-abstraction *ideas* at the wallet layer** (no consensus change):
  social recovery (multisig/Shamir of the seed), daily spending limits, session
  keys for apps, child/allowance accounts, business accounts with employee
  permissions, subscription approval rules, one-click checkout authorization.
- 🟢 Merchant-pays-fee / sponsored sends via an app-layer relay (not on-chain gas).

**Network depth**
- 🟡 Node roles (seed / API / miner / explorer / archive), seed crawler + DNS seed
  records, peer scoring/latency/version tracking, bad-peer cooldown, auto peer rotation.
- 🟡 Pruned-node mode, archive-node mode, snapshot bootstrap, health alerts, Grafana
  dashboard, log viewer, node upgrade checker, one-command install/backup/rollback.
- 🟡 Mining: pool mining, solo mining, mining-pool API, Stratum-like protocol,
  profitability estimate, miner logs/timeout improvements.
- 🔴 Headers-first sync, assume-valid checkpoints, UTXO snapshots as a consensus
  concept, compact block relay improvements, package relay, reorg-protection tuning,
  chainstate DB backend — core-node work; sequence carefully.

**Governance / Treasury track** (runs alongside from Phase 0)
- 🟢 Proposal system, community voting, bounty board, grant applications, milestone
  payouts, public spending reports, governance forum.
- 🟡 Multisig treasury, protocol-upgrade voting/signaling.
- 🟢 NIP index (below).

**Privacy depth** (opt-in, auditable, never forced)
- 🟡 Tor / I2P node mode, private transaction relay, wallet privacy score, coin control.
- 🟢 View keys for auditors (prove history without revealing the key).
- 🟡 Stealth receive addresses / reusable payment codes / silent-payments-style receive.
- 🔴 CoinJoin / PayJoin coordination (needs careful design).

## Phase 4 — Scale (later)

- 🟡 Light clients, API read replicas, explorer indexer scaling, better DB backend,
  fast sync, snapshot sync.
- 🔴 Payment channels / instant "Instant Mode" payments, watchtowers, channel
  explorer/backups (Lightning-style) — large, consensus + off-chain protocol.

---

# 🔴 Research shelf (audit + more contributors required)

Not abandoned — deliberately parked so the core doesn't rot while these are
explored. Each is a multi-quarter-to-multi-year effort that needs a security audit
before touching real value:

- **Smart-contract VM / EVM-compatible sidechain / WASM programs / Solana-style
  programs.** Start and stay with *contract templates* until there's an audited VM plan.
- **Real privacy cryptography:** Monero-style ring signatures + confidential
  amounts; Zcash-style shielded pool / zero-knowledge proofs. Shipping unaudited,
  hand-rolled privacy crypto is worse than none.
- **On-chain account abstraction** (ERC-4337-style bundlers/paymasters). Do the
  *wallet-layer* versions in Phase 3 instead.
- **Cross-chain bridges / IBC / wrapped NET / cross-chain swaps.** Safer precursors:
  atomic swaps, a wrapped-NET *test* bridge, a proof-of-reserve dashboard, explicit
  bridge-risk warnings.
- **DeFi:** DEX/AMM, lending, borrowing, yield vaults, synthetics, options/futures.
  Start with escrow, simple swaps, prediction-market demo, treasury bounties,
  community crowdfunding — do **not** rush lending/yield.
- **Hardware wallet support**, DLC-style conditional contracts.

# Anti-goals (what keeps NetCoin from becoming master-of-none)

- ❌ Don't put tokens / contracts / privacy / channels **into the base chain**.
  Keep the base a simple, secure money layer; layer power on top.
- ❌ Don't force privacy, tokens, or advanced features on normal users.
- ❌ Don't ship unaudited privacy/VM crypto to anything holding value.
- ❌ Don't chase feature-parity with Ethereum/Monero. The winnable identity is
  **"the easiest chain to understand, run yourself, and build on."**

# NetCoin Improvement Proposals (NIP index)

| NIP | Title | Phase |
|---|---|---|
| NIP-0001 | Improvement process itself | 0 |
| NIP-0002 | Wallet safety standard | 0–1 |
| NIP-0003 | App-layer token standard (NET-20/721/1155) | 3 |
| NIP-0004 | Public node / API standard (+ auth) | 0–2 |
| NIP-0005 | Upgrade-activation standard (height-gated) | 0 |
| NIP-0006 | Contract-template standard (escrow/timelock/multisig) | 3 |
| NIP-0007 | Optional-privacy standard (address non-reuse, view keys) | 1 / 3 |

# How to decide any future feature (keep it coherent)

For anything proposed, ask in order:
1. **What color is it?** 🔴 → research shelf unless truly essential. 🟢/🟡 → fair game.
2. **Which mode does it live in?** If it doesn't fit Simple / Merchant / Developer /
   Node / Governance, it isn't ready.
3. **Turn-it-off test:** does simple Send/Receive/Balance still work with it disabled?
   If not, it's in the wrong layer.
