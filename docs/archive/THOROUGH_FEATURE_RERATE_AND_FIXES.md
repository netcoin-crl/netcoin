# NetCoin feature rerate — current main

Scale: 1 skeletal, 5 usable testnet/demo, 7 strong, 8 keyboard-validated strong, 10 externally audited/professional.

Summary: 69 rated features, average 7.15/10, 52 features rated 7+, 0 below 6.

Important caveat: ratings are internal readiness ratings for a public-testnet educational project. They are not an external security audit, legal review, exchange-readiness claim, or mainnet-readiness claim.

## Category summary

| Category | Count | Average |
|---|---:|---:|
| Core chain | 14 | 7.43/10 |
| Crypto | 5 | 6.4/10 |
| Storage | 6 | 6.67/10 |
| Wallet | 8 | 6.88/10 |
| Node/API | 11 | 7.36/10 |
| Security | 5 | 6.8/10 |
| Sites | 10 | 7.55/10 |
| Architecture | 1 | 8.0/10 |
| Markets | 4 | 7.0/10 |
| Mining | 1 | 8.0/10 |
| Exchange | 3 | 6.57/10 |
| Faucet | 1 | 8.0/10 |

## Core chain

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| UTXO blockchain | 8.0/10 | strong | Real UTXO chain with validation, persistence, and tests. | External consensus audit. |
| Block and transaction model | 8.0/10 | strong | Bitcoin-style blocks, tx ids, raw encoding, and signing paths. | More frozen invalid vectors. |
| Proof-of-work mining | 7.0/10 | solid | Functional PoW miner and block submission workflow. | More multi-node mining soak tests. |
| Difficulty adjustment | 7.0/10 | solid | Retargeting and timestamp tests exist. | More adversarial timestamp simulations. |
| Coinbase rewards and maturity | 8.0/10 | strong | Emission schedule and maturity checks are implemented and tested. | Longer halving/reduction vector set. |
| Reorg handling | 8.0/10 | strong | Rollback and revalidation are covered by tests. | Reorg-aware app-index stress tests. |
| Consensus versioning | 7.5/10 | strong | Dedicated consensus module with activation-height design and testnet-only versionbits rehearsal support. | Public deployment governance process and longer rehearsal history. |
| Protocol specification | 8.0/10 | strong | docs/spec covers block, transaction, sighash, scripts, addresses, fork choice, difficulty, emission, mempool policy, P2P, API, code paths, and parity vectors. | Freeze more external audit vectors against the spec. |
| Versionbits rehearsal | 8.0/10 | strong | Testnet/regtest-only versionbits state machine reads real block versions, localnet rehearses STARTED -> LOCKED_IN -> ACTIVE, and mainnet hard-refuses wiring. | Run an operator-approved public-testnet rehearsal and archive the report. |
| Genesis rehearsal | 7.0/10 | solid | Regtest/testnet-rehearsal genesis generator validates manifests, mines height-zero blocks, writes reports, and hard-refuses mainnet. | Full ceremony drill with independent reviewers; mainnet remains governance-gated. |
| Chainstate hash | 7.0/10 | solid | UTXO commitment/hash command helps verify deterministic state. | Publish checkpoints from multiple nodes. |
| Invalid block/tx corpuses | 6.5/10 | improving | Fixtures exist but should grow. | Add hundreds of malformed corpus cases. |
| Mutation smoke tests | 6.0/10 | basic | Consensus mutation smoke exists, not a full mutation framework. | Wire deeper mutation testing into nightly CI. |
| Performance benchmarks | 8.0/10 | strong | Block validation, restart replay, memory, and mempool-accept benchmark reports have thresholds, docs, Make target, and CI workflow wiring. | Trend benchmark history across GitHub and seed hardware. |

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
| Browser wallet | 7.5/10 | solid | Hosted non-custodial wallet has encrypted profiles, private-key sign-in, vault module, address-type balances, PSBT/airgap tooling, and core send/receive flows. | Clean account switcher and full Playwright account/sign-in coverage. |
| Signer abstraction | 7.0/10 | solid | Hot, watch-only, offline, test, and hardware-stub signers exist. | Implement real hardware adapter. |
| Hardware signer | 6.0/10 | improving | External command/file transport adapters support real hardware-signer bridges plus test simulation. | Add native HID/vendor adapters for specific devices. |
| Coin control | 7.0/10 | solid | Freeze/unfreeze and selection helpers exist. | Surface coin control in browser wallet. |
| Transaction simulator/risk | 8.0/10 | strong | Send UI now shows a risk simulator with balance-after, change, input count, fee-rate, and blocking decisions. | Persist risk reports into approval queue. |
| Dynamic fee / RBF | 6.0/10 | basic | Fee estimation and bump helpers exist but are simple. | Mempool-pressure driven fee UI. |

## Node/API

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| HTTP API | 7.0/10 | solid | Broad node/app API with auth and tests. | Deep OpenAPI schema parity. |
| Versioned API and SDKs | 8.0/10 | strong | /v1 aliases, deprecation headers, OpenAPI checker, Python SDK, JS SDK, and Rust SDK smoke coverage exercise local nodes. | Registry publication dry-runs and generated client contract tests. |
| CLI | 8.0/10 | strong | Large practical command surface. | Group commands with help profiles. |
| JSON-RPC | 6.0/10 | testnet | Functional but not mature RPC parity. | Add RPC compatibility test matrix. |
| P2P | 7.0/10 | solid | PeerManager, peerdb, scoring, bans, sync scheduler, bad-header peer penalties, localnet harness, and relay probes exist. | Integrate full binary block relay under adversarial soak tests. |
| Headers sync | 7.0/10 | solid | Linked-header validation, checkpoints, peer chainwork tracking, stalled retries, and peerdb assignment exist. | Run multi-peer adversarial sync soak tests. |
| Metrics and incidents | 8.0/10 | strong | Prometheus metrics, Grafana dashboard JSON, status uptime history, health summaries, incidents, and runbooks exist. | Deploy public dashboard screenshots and alert-routing examples. |
| Bandwidth enforcement | 8.0/10 | strong | Outbound relay token buckets enforce home/low bandwidth budgets, expose metrics/status, and have localnet sustained-throughput probes. | Run longer flood tests on public-testnet staging nodes. |
| DNS seeder | 6.0/10 | ops-ceiling | Stdlib UDP DNS seeder serves health-filtered A records from peerdb and passes real-query/localnet tests. | Independent domains/operators are needed before this can honestly exceed the ops ceiling. |
| Node installer and upgrades | 8.0/10 | strong | Install, uninstall, and upgrade scripts have dry-run safety tests plus a CI compose smoke that starts a node, waits for /info, mines, and tears down. | Run upgrade drills on staging seed hosts before every tagged release. |
| Rate limiting | 8.0/10 | strong | Per key/IP token buckets return 429 with Retry-After, anonymize API-key identities, and have loadtest proof that limits hold. | Expose rate-limit dashboards and per-scope policy controls. |

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
| Shared site shell | 8.2/10 | strong | Sleek shared navigation, compact directory, cache-busted shared shell, and audit-backed sync across 24 sites. | Add screenshot diff checks for desktop/mobile shell regressions. |
| Feature discoverability | 8.3/10 | strong | Searchable Features site, /api/features catalog, live wiring probes, global directory, and site search expose the tool map. | Generate docs and feature cards directly from one catalog source. |
| Community posts | 7.0/10 | solid | Reddit-style cards and posting flow exist. | Functional vote/comment/mod queue. |
| Leaderboards | 7.0/10 | solid | Readable top-miner/earner/donor tables. | Sort/export/search by table. |
| Docs/Learn | 8.0/10 | strong | Strong educational docs and setup flows. | Keep docs generated from feature catalog. |
| Explorer UI | 8.0/10 | strong | Explorer has address/tx/block/mempool surfaces, pagination/CSV hooks, reorg/orphan watch, event payloads, and indexer APIs. | Load-test explorer endpoints and wire richer graph profiles into the UI. |
| Operator dashboard | 7.5/10 | solid | Dedicated health-center UI summarizes sites, API coverage, release trust, node metrics, and alerts. | Add live log tail and backup restore drills. |
| Exchange dashboard | 7.0/10 | solid | Dedicated custody UI explains deposit/withdrawal states and reserve readiness. | Connect to live deposit/withdrawal tables. |
| Wallet UI | 7.5/10 | solid | Browser wallet has profile unlock, recovery, private-key sign-in, address-type balances, PSBT/QR tools, and cleaner shell without the extra safety panel. | Build the account switcher and persist send-review approvals. |
| Accessibility | 7.0/10 | improving | Cleaner semantics and site audit coverage exist, but a full automated a11y matrix is still pending. | Add axe/Playwright accessibility checks. |

## Architecture

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Hybrid language upgrade space | 8.0/10 | strong | Rust/TypeScript/Python directories, manifest, API, website, and checks define the final professional system layout. | Freeze vectors and begin Rust core parity implementation. |

## Markets

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| CLOB prediction markets | 7.0/10 | solid | Orderbook, order types, ticker, trades, and portfolio exist. | Stress test matching engine and settlement. |
| Oracle/evidence/disputes | 7.0/10 | solid | Evidence registry, oracle votes, dispute timeline, and integrity checks exist. | Add resolver/reputation UI. |
| Settlement reconciliation | 7.0/10 | solid | Settlement audit and reconciliation helpers exist. | End-to-end settlement tests with edge cases. |
| Market-maker tools | 7.0/10 | improving | Quote planning and risk helpers exist. | Add dry-run bot dashboard. |

## Mining

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Stratum-lite pool | 8.0/10 | strong | TCP getwork/submit pool validates shares, accepts mined blocks, tracks per-miner accounting, creates payout plans, exposes CLI flags, and passes localnet probe tests. | Add pooled payout transaction construction and longer multi-miner soak. |

## Exchange

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Deposit/withdrawal states | 6.5/10 | improving | Exchange state machines and accounting exist. | Reorg-backed integration against live node. |
| Proof of reserves | 7.0/10 | solid | Merkle liabilities and attestation tools exist. | Public verification page. |
| Production custody | 6.2/10 | improving | Hot/cold custody accounts, approval thresholds, hot-wallet coverage, and cold-to-hot transfer tracking exist. | Connect to real cold signer and operator dashboard. |

## Faucet

| Feature | Rating | Status | Notes | Next fix |
|---|---:|---|---|---|
| Faucet hardening | 8.0/10 | strong | Proof-of-work challenge, autoscaling difficulty, reputation scoring, device hints, daily cap, abuse summary, admin audit log, and CAPTCHA hooks exist. | Add hosted CAPTCHA provider keys; CAPTCHA itself remains ops-secret capped. |

## Current top impact fixes

| # | Area | Fix | Impact |
|---:|---|---|---|
| 1 | Protocol | Completed: docs/spec now anchors consensus, policy, P2P, API, code paths, and parity-vector references. | Protocol spec 2 -> 8 |
| 2 | Network | Completed: bandwidth enforcement, DNS seeder, Stratum-lite pool, rate limiting, and node installer smoke coverage are real. | Network/P2P package set 4-6 -> 6-8 |
| 3 | API/SDK | Completed: /v1 aliases, OpenAPI source checker, Python/JS SDK smoke tests, and Rust SDK crate coverage. | Versioned API/SDK 4-6 -> 8 |
| 4 | Product surfaces | Completed: explorer pagination/CSV/reorg watch, faucet autoscaling/admin audit, status uptime history, Prometheus docs, and Grafana dashboard. | Explorer/Faucet/Status metrics 5-7 -> 8 |
| 5 | Release/testing | Completed: performance benchmark tool and CI workflow with regression thresholds. | Perf evidence 2 -> 8 |
| 6 | Activation safety | Completed: testnet-only versionbits rehearsal and genesis rehearsal both hard-refuse mainnet wiring. | Versionbits/genesis rehearsal 1-2 -> 7-8 |
| 7 | Wallet | Completed: private-key sign-in already exists; next make it a first-class account/profile switcher. | Wallet UI 7 -> 7.5 now, 8 with account UX |
| 8 | Sites | Completed: 24-site shell sync, cache-busted shared shell, clean site audit, and searchable feature catalog. | Sites/discoverability 8 -> 8.3 |
| 9 | Custody/markets | Exchange custody and markets remain useful testnet demos; next jump requires live accounting tables, settlement soak, and resolver reputation UI. | Exchange/markets mostly 6.5-7 |
| 10 | Quality | Remaining honest blockers are external audit, long-running fuzz/soak history, independent DNS/ops, CAPTCHA secrets, and physical hardware-wallet transcripts. | Caps several areas below professional 9-10 |
