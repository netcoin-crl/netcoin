# NetCoin thorough feature re-rate and 10 impact fixes

Scale: 1 skeletal, 5 usable testnet/demo, 7 strong, 10 audited/professional.

Summary: 56 rated features, average 6.78/10, 35 features rated 7+, 2 below 6.

## Core chain

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| UTXO blockchain | 8.0/10 | strong | Real UTXO chain with validation, persistence, and tests. | External consensus audit. |
| Block and transaction model | 8.0/10 | strong | Bitcoin-style blocks, tx ids, raw encoding, and signing paths. | More frozen invalid vectors. |
| Proof-of-work mining | 7.0/10 | solid | Functional PoW miner and block submission workflow. | More multi-node mining soak tests. |
| Difficulty adjustment | 7.0/10 | solid | Retargeting and timestamp tests exist. | More adversarial timestamp simulations. |
| Coinbase rewards and maturity | 8.0/10 | strong | Emission schedule and maturity checks are implemented and tested. | Longer halving/reduction vector set. |
| Reorg handling | 8.0/10 | strong | Rollback and revalidation are covered by tests. | Reorg-aware app-index stress tests. |
| Consensus versioning | 7.0/10 | solid | Dedicated consensus module with activation-height design. | Public deployment governance process. |
| Chainstate hash | 7.0/10 | solid | UTXO commitment/hash command helps verify deterministic state. | Publish checkpoints from multiple nodes. |
| Invalid block/tx corpuses | 6.5/10 | improving | Fixtures exist but should grow. | Add hundreds of malformed corpus cases. |
| Mutation smoke tests | 6.0/10 | basic | Consensus mutation smoke exists, not a full mutation framework. | Wire deeper mutation testing into nightly CI. |

## Crypto

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| ECDSA/secp256k1 signing | 7.0/10 | solid | Audited backend is preferred when installed; pure Python fallback is labeled reference. | Require audited backend for production builds. |
| Schnorr/Taproot-style support | 6.0/10 | testnet | Useful educational implementation, not Bitcoin-equivalent Taproot. | More BIP340/BIP341 vector coverage. |
| Script VM | 6.0/10 | testnet | Educational Script VM with common templates. | Separate consensus script flags and policy flags. |
| Multisig and timelocks | 6.0/10 | testnet | Useful helper flows and scripts. | Better wallet UI and policy checks. |
| Crypto self-test | 7.0/10 | solid | Startup-visible self-test helps catch broken crypto paths. | Expose self-test in status page. |

## Storage

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| SQLite default backend | 7.0/10 | solid | SQLite is the default with WAL/busy-timeout hardening. | More crash-kill tests under concurrency. |
| JSON legacy backend | 6.0/10 | demo | Useful for fixtures and demos, not recommended for public nodes. | Keep JSON as export-only long term. |
| Migrations | 6.5/10 | improving | Migration table and helpers exist. | Version every chain/app/index schema. |
| Backup/restore/reindex | 6.5/10 | solid | Operator commands exist. | Add restore-drill automation. |
| Production indexer | 7.0/10 | solid | Address, mempool, graph, and integrity helpers exist. | Wire more indexer data into explorer pages. |
| Explorer watchlists | 7.0/10 | solid | Watch/notification layer exists. | Add browser notification UI. |

## Wallet

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Encrypted wallet files | 7.0/10 | solid | Encrypted wallet storage and migration tests exist. | External wallet security review. |
| HD wallet / recovery | 6.5/10 | improving | HD paths, gap scanning, and recovery reports exist. | Move toward standard mnemonic compatibility. |
| Browser wallet | 7.0/10 | solid | Local browser wallet with vault module and core flows. | Full Playwright coverage and stronger vault UX. |
| Signer abstraction | 7.0/10 | solid | Hot, watch-only, offline, test, and hardware-stub signers exist. | Implement real hardware adapter. |
| Hardware signer | 3.0/10 | placeholder | Interface exists but no real hardware integration. | Add a real HID/QR hardware signer adapter. |
| Coin control | 7.0/10 | solid | Freeze/unfreeze and selection helpers exist. | Surface coin control in browser wallet. |
| Transaction simulator/risk | 7.0/10 | solid | Preview, warnings, and approval queue exist. | Make risky-send approval part of send UI. |
| Dynamic fee / RBF | 6.0/10 | basic | Fee estimation and bump helpers exist but are simple. | Mempool-pressure driven fee UI. |

## Node/API

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| HTTP API | 7.0/10 | solid | Broad node/app API with auth and tests. | Deep OpenAPI schema parity. |
| CLI | 8.0/10 | strong | Large practical command surface. | Group commands with help profiles. |
| JSON-RPC | 6.0/10 | testnet | Functional but not mature RPC parity. | Add RPC compatibility test matrix. |
| P2P | 6.0/10 | improving | PeerManager, peerdb, scoring, bans, and sync helpers exist. | Real binary peer protocol hardening. |
| Headers sync | 6.0/10 | improving | Header scheduler and retry helpers exist. | Full block-download pipeline integration. |
| Metrics and incidents | 7.0/10 | solid | Metrics history, health summaries, incidents, and runbooks exist. | Add Grafana dashboard fixtures. |

## Security

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Signed app envelopes | 7.0/10 | solid | Sensitive writes are bound to method/path/body/timestamp/nonce. | SDK-first signed write examples on every write page. |
| API keys / RBAC | 6.5/10 | improving | Scoped key structures and role helpers exist. | Add admin UI for scopes and key revocation. |
| Webhook HMAC / SSRF | 7.0/10 | solid | HMAC and SSRF checks are tested. | Expose delivery dead-letter UI. |
| Release SBOM/provenance | 7.0/10 | solid | SBOM, signing, and provenance tools exist. | Adopt Sigstore/GitHub attestations in CI. |
| Professional readiness/audit | 6.5/10 | structural | Manifest and audit scripts catch missing workstreams. | External audit and long public testnet. |

## Sites

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Shared site shell | 8.0/10 | strong | Sleek shared navigation and feature launcher across sites. | Automated shell sync checks. |
| Feature discoverability | 8.0/10 | strong | Global feature launcher exposes key tools. | Add searchable full feature directory. |
| Community posts | 7.0/10 | solid | Reddit-style cards and posting flow exist. | Functional vote/comment/mod queue. |
| Leaderboards | 7.0/10 | solid | Readable top-miner/earner/donor tables. | Sort/export/search by table. |
| Docs/Learn | 8.0/10 | strong | Strong educational docs and setup flows. | Keep docs generated from feature catalog. |
| Explorer UI | 7.0/10 | solid | Good explorer surface; indexer APIs exist. | Wire rich indexer profiles into UI. |
| Wallet UI | 7.0/10 | solid | Browser wallet and recovery shortcuts exist. | Integrate approval queue and simulator UX. |
| Accessibility | 6.5/10 | improving | Cleaner semantics but needs full a11y pass. | Add axe/Playwright accessibility checks. |

## Markets

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| CLOB prediction markets | 7.0/10 | solid | Orderbook, order types, ticker, trades, and portfolio exist. | Stress test matching engine and settlement. |
| Oracle/evidence/disputes | 7.0/10 | solid | Evidence registry, oracle votes, dispute timeline, and integrity checks exist. | Add resolver/reputation UI. |
| Settlement reconciliation | 7.0/10 | solid | Settlement audit and reconciliation helpers exist. | End-to-end settlement tests with edge cases. |
| Market-maker tools | 6.5/10 | improving | Quote planning and risk helpers exist. | Add dry-run bot dashboard. |

## Exchange

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Deposit/withdrawal states | 6.5/10 | improving | Exchange state machines and accounting exist. | Reorg-backed integration against live node. |
| Proof of reserves | 7.0/10 | solid | Merkle liabilities and attestation tools exist. | Public verification page. |
| Production custody | 4.5/10 | weak | Still not exchange-grade hot/cold custody. | Multi-operator approvals and cold signer workflow. |

## Faucet

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Faucet hardening | 6.5/10 | improving | Basic public-testnet controls exist. | Proof-of-work/CAPTCHA/reputation dashboard. |

## 10 biggest impact fixes applied in this pass

| # | Fix | What changed |
|---:|---|---|
| 1 | Community post voting | Added backend post votes, idempotent voter tracking, and working UI up/down buttons. |
| 2 | Community comments | Added post comment endpoints and a Comments tab. |
| 3 | Community moderation queue | Added report queue, hide/review actions, and Mod queue UI. |
| 4 | Hot/new/top post sorting | Added Reddit-like feed ranking and sort pills. |
| 5 | Readable leaderboards+summary | Added leaderboard ranks, short IDs, totals, and UI summary chips. |
| 6 | Unified feature catalog API | Added netcoin/feature_catalog.py and /api/features. |
| 7 | Searchable Features site | Added sites/features with all ratings, category filters, and top fixes. |
| 8 | Feature launcher coverage | Added Features to shared site shell and search routing. |
| 9 | Shared-shell sync tool | Added tools/sync_site_assets.py and make site-sync. |
| 10 | Site UI audit tool | Added tools/audit_site_ui.py, make site-audit, and regression tests. |