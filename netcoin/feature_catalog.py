"""Public feature catalog and rating data for NetCoin.

The catalog is deliberately small-data/static so the public websites, API docs,
and audit reports can render the same feature inventory without hand-copying
wordy page text. Ratings use NetCoin's internal review scale:
1 skeletal, 5 usable testnet/demo, 7 strong implementation, 10 audited/pro-grade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class FeatureRating:
    category: str
    name: str
    rating: float
    status: str
    summary: str
    next_fix: str = ""


_FEATURES: tuple[FeatureRating, ...] = (
    # Chain / consensus
    FeatureRating(
        "Core chain",
        "UTXO blockchain",
        8.0,
        "strong",
        "Real UTXO chain with validation, persistence, and tests.",
        "External consensus audit.",
    ),
    FeatureRating(
        "Core chain",
        "Block and transaction model",
        8.0,
        "strong",
        "Bitcoin-style blocks, tx ids, raw encoding, and signing paths.",
        "More frozen invalid vectors.",
    ),
    FeatureRating(
        "Core chain",
        "Proof-of-work mining",
        7.0,
        "solid",
        "Functional PoW miner and block submission workflow.",
        "More multi-node mining soak tests.",
    ),
    FeatureRating(
        "Core chain",
        "Difficulty adjustment",
        7.0,
        "solid",
        "Retargeting and timestamp tests exist.",
        "More adversarial timestamp simulations.",
    ),
    FeatureRating(
        "Core chain",
        "Coinbase rewards and maturity",
        8.0,
        "strong",
        "Emission schedule and maturity checks are implemented and tested.",
        "Longer halving/reduction vector set.",
    ),
    FeatureRating(
        "Core chain",
        "Reorg handling",
        8.0,
        "strong",
        "Rollback and revalidation are covered by tests.",
        "Reorg-aware app-index stress tests.",
    ),
    FeatureRating(
        "Core chain",
        "Consensus versioning",
        7.5,
        "strong",
        "Dedicated consensus module with activation-height design and testnet-only versionbits rehearsal support.",
        "Public deployment governance process and longer rehearsal history.",
    ),
    FeatureRating(
        "Core chain",
        "Protocol specification",
        8.0,
        "strong",
        "docs/spec covers block, transaction, sighash, scripts, addresses, fork choice, difficulty, emission, mempool policy, P2P, API, code paths, and parity vectors.",
        "Freeze more external audit vectors against the spec.",
    ),
    FeatureRating(
        "Core chain",
        "Versionbits rehearsal",
        8.0,
        "strong",
        "Testnet/regtest-only versionbits state machine reads real block versions, localnet rehearses STARTED -> LOCKED_IN -> ACTIVE, and mainnet hard-refuses wiring.",
        "Run an operator-approved public-testnet rehearsal and archive the report.",
    ),
    FeatureRating(
        "Core chain",
        "Genesis rehearsal",
        7.0,
        "solid",
        "Regtest/testnet-rehearsal genesis generator validates manifests, mines height-zero blocks, writes reports, and hard-refuses mainnet.",
        "Full ceremony drill with independent reviewers; mainnet remains governance-gated.",
    ),
    FeatureRating(
        "Core chain",
        "Chainstate hash",
        7.0,
        "solid",
        "UTXO commitment/hash command helps verify deterministic state.",
        "Publish checkpoints from multiple nodes.",
    ),
    FeatureRating(
        "Core chain",
        "Invalid block/tx corpuses",
        6.5,
        "improving",
        "Fixtures exist but should grow.",
        "Add hundreds of malformed corpus cases.",
    ),
    FeatureRating(
        "Core chain",
        "Mutation smoke tests",
        6.0,
        "basic",
        "Consensus mutation smoke exists, not a full mutation framework.",
        "Wire deeper mutation testing into nightly CI.",
    ),
    FeatureRating(
        "Core chain",
        "Performance benchmarks",
        8.0,
        "strong",
        "Block validation, restart replay, memory, and mempool-accept benchmark reports have thresholds, docs, Make target, and CI workflow wiring.",
        "Trend benchmark history across GitHub and seed hardware.",
    ),
    # Crypto / script
    FeatureRating(
        "Crypto",
        "ECDSA/secp256k1 signing",
        7.0,
        "solid",
        "Audited backend is preferred when installed; pure Python fallback is labeled reference.",
        "Require audited backend for production builds.",
    ),
    FeatureRating(
        "Crypto",
        "Schnorr/Taproot-style support",
        6.0,
        "testnet",
        "Useful educational implementation, not Bitcoin-equivalent Taproot.",
        "More BIP340/BIP341 vector coverage.",
    ),
    FeatureRating(
        "Crypto",
        "Script VM",
        6.0,
        "testnet",
        "Educational Script VM with common templates.",
        "Separate consensus script flags and policy flags.",
    ),
    FeatureRating(
        "Crypto",
        "Multisig and timelocks",
        6.0,
        "testnet",
        "Useful helper flows and scripts.",
        "Better wallet UI and policy checks.",
    ),
    FeatureRating(
        "Crypto",
        "Crypto self-test",
        7.0,
        "solid",
        "Startup-visible self-test helps catch broken crypto paths.",
        "Expose self-test in status page.",
    ),
    # Storage/indexer
    FeatureRating(
        "Storage",
        "SQLite default backend",
        7.0,
        "solid",
        "SQLite is the default with WAL/busy-timeout hardening.",
        "More crash-kill tests under concurrency.",
    ),
    FeatureRating(
        "Storage",
        "JSON legacy backend",
        6.0,
        "demo",
        "Useful for fixtures and demos, not recommended for public nodes.",
        "Keep JSON as export-only long term.",
    ),
    FeatureRating(
        "Storage",
        "Migrations",
        6.5,
        "improving",
        "Migration table and helpers exist.",
        "Version every chain/app/index schema.",
    ),
    FeatureRating(
        "Storage", "Backup/restore/reindex", 6.5, "solid", "Operator commands exist.", "Add restore-drill automation."
    ),
    FeatureRating(
        "Storage",
        "Production indexer",
        7.0,
        "solid",
        "Address, mempool, graph, and integrity helpers exist.",
        "Wire more indexer data into explorer pages.",
    ),
    FeatureRating(
        "Storage",
        "Explorer watchlists",
        7.0,
        "solid",
        "Watch/notification layer exists.",
        "Add browser notification UI.",
    ),
    # Wallet
    FeatureRating(
        "Wallet",
        "Encrypted wallet files",
        7.0,
        "solid",
        "Encrypted wallet storage and migration tests exist.",
        "External wallet security review.",
    ),
    FeatureRating(
        "Wallet",
        "HD wallet / recovery",
        6.5,
        "improving",
        "HD paths, gap scanning, and recovery reports exist.",
        "Move toward standard mnemonic compatibility.",
    ),
    FeatureRating(
        "Wallet",
        "Browser wallet",
        7.5,
        "solid",
        "Hosted non-custodial wallet has encrypted profiles, private-key sign-in, vault module, address-type balances, PSBT/airgap tooling, and core send/receive flows.",
        "Clean account switcher and full Playwright account/sign-in coverage.",
    ),
    FeatureRating(
        "Wallet",
        "Signer abstraction",
        7.0,
        "solid",
        "Hot, watch-only, offline, test, and hardware-stub signers exist.",
        "Implement real hardware adapter.",
    ),
    FeatureRating(
        "Wallet",
        "Hardware signer",
        6.0,
        "improving",
        "External command/file transport adapters support real hardware-signer bridges plus test simulation.",
        "Add native HID/vendor adapters for specific devices.",
    ),
    FeatureRating(
        "Wallet",
        "Coin control",
        7.0,
        "solid",
        "Freeze/unfreeze and selection helpers exist.",
        "Surface coin control in browser wallet.",
    ),
    FeatureRating(
        "Wallet",
        "Transaction simulator/risk",
        8.0,
        "strong",
        "Send UI now shows a risk simulator with balance-after, change, input count, fee-rate, and blocking decisions.",
        "Persist risk reports into approval queue.",
    ),
    FeatureRating(
        "Wallet",
        "Dynamic fee / RBF",
        6.0,
        "basic",
        "Fee estimation and bump helpers exist but are simple.",
        "Mempool-pressure driven fee UI.",
    ),
    # Node/API/P2P
    FeatureRating(
        "Node/API", "HTTP API", 7.0, "solid", "Broad node/app API with auth and tests.", "Deep OpenAPI schema parity."
    ),
    FeatureRating(
        "Node/API",
        "Versioned API and SDKs",
        8.0,
        "strong",
        "/v1 aliases, deprecation headers, OpenAPI checker, Python SDK, JS SDK, and Rust SDK smoke coverage exercise local nodes.",
        "Registry publication dry-runs and generated client contract tests.",
    ),
    FeatureRating(
        "Node/API", "CLI", 8.0, "strong", "Large practical command surface.", "Group commands with help profiles."
    ),
    FeatureRating(
        "Node/API",
        "JSON-RPC",
        6.0,
        "testnet",
        "Functional but not mature RPC parity.",
        "Add RPC compatibility test matrix.",
    ),
    FeatureRating(
        "Node/API",
        "P2P",
        7.0,
        "solid",
        "PeerManager, peerdb, scoring, bans, sync scheduler, bad-header peer penalties, localnet harness, and relay probes exist.",
        "Integrate full binary block relay under adversarial soak tests.",
    ),
    FeatureRating(
        "Node/API",
        "Headers sync",
        7.0,
        "solid",
        "Linked-header validation, checkpoints, peer chainwork tracking, stalled retries, and peerdb assignment exist.",
        "Run multi-peer adversarial sync soak tests.",
    ),
    FeatureRating(
        "Node/API",
        "Metrics and incidents",
        8.0,
        "strong",
        "Prometheus metrics, Grafana dashboard JSON, status uptime history, health summaries, incidents, and runbooks exist.",
        "Deploy public dashboard screenshots and alert-routing examples.",
    ),
    FeatureRating(
        "Node/API",
        "Bandwidth enforcement",
        8.0,
        "strong",
        "Outbound relay token buckets enforce home/low bandwidth budgets, expose metrics/status, and have localnet sustained-throughput probes.",
        "Run longer flood tests on public-testnet staging nodes.",
    ),
    FeatureRating(
        "Node/API",
        "DNS seeder",
        6.0,
        "ops-ceiling",
        "Stdlib UDP DNS seeder serves health-filtered A records from peerdb and passes real-query/localnet tests.",
        "Independent domains/operators are needed before this can honestly exceed the ops ceiling.",
    ),
    FeatureRating(
        "Node/API",
        "Node installer and upgrades",
        8.0,
        "strong",
        "Install, uninstall, and upgrade scripts have dry-run safety tests plus a CI compose smoke that starts a node, waits for /info, mines, and tears down.",
        "Run upgrade drills on staging seed hosts before every tagged release.",
    ),
    FeatureRating(
        "Node/API",
        "Rate limiting",
        8.0,
        "strong",
        "Per key/IP token buckets return 429 with Retry-After, anonymize API-key identities, and have loadtest proof that limits hold.",
        "Expose rate-limit dashboards and per-scope policy controls.",
    ),
    # App security/product
    FeatureRating(
        "Security",
        "Signed app envelopes",
        7.0,
        "solid",
        "Sensitive writes are bound to method/path/body/timestamp/nonce.",
        "SDK-first signed write examples on every write page.",
    ),
    FeatureRating(
        "Security",
        "API keys / RBAC",
        6.5,
        "improving",
        "Scoped key structures and role helpers exist.",
        "Add admin UI for scopes and key revocation.",
    ),
    FeatureRating(
        "Security",
        "Webhook HMAC / SSRF",
        7.0,
        "solid",
        "HMAC and SSRF checks are tested.",
        "Expose delivery dead-letter UI.",
    ),
    FeatureRating(
        "Security",
        "Release SBOM/provenance",
        7.0,
        "solid",
        "SBOM, signing, and provenance tools exist.",
        "Adopt Sigstore/GitHub attestations in CI.",
    ),
    FeatureRating(
        "Security",
        "Professional readiness/audit",
        6.5,
        "structural",
        "Manifest and audit scripts catch missing workstreams.",
        "External audit and long public testnet.",
    ),
    # Community/sites
    FeatureRating(
        "Sites",
        "Shared site shell",
        8.2,
        "strong",
        "Sleek shared navigation, compact directory, cache-busted shared shell, and audit-backed sync across 24 sites.",
        "Add screenshot diff checks for desktop/mobile shell regressions.",
    ),
    FeatureRating(
        "Sites",
        "Feature discoverability",
        8.3,
        "strong",
        "Searchable Features site, /api/features catalog, live wiring probes, global directory, and site search expose the tool map.",
        "Generate docs and feature cards directly from one catalog source.",
    ),
    FeatureRating(
        "Architecture",
        "Hybrid language upgrade space",
        8.0,
        "strong",
        "Rust/TypeScript/Python directories, manifest, API, website, and checks define the final professional system layout.",
        "Freeze vectors and begin Rust core parity implementation.",
    ),
    FeatureRating(
        "Sites",
        "Community posts",
        7.0,
        "solid",
        "Reddit-style cards and posting flow exist.",
        "Functional vote/comment/mod queue.",
    ),
    FeatureRating(
        "Sites", "Leaderboards", 7.0, "solid", "Readable top-miner/earner/donor tables.", "Sort/export/search by table."
    ),
    FeatureRating(
        "Sites",
        "Docs/Learn",
        8.0,
        "strong",
        "Strong educational docs and setup flows.",
        "Keep docs generated from feature catalog.",
    ),
    FeatureRating(
        "Sites",
        "Explorer UI",
        8.0,
        "strong",
        "Explorer has address/tx/block/mempool surfaces, pagination/CSV hooks, reorg/orphan watch, event payloads, and indexer APIs.",
        "Load-test explorer endpoints and wire richer graph profiles into the UI.",
    ),
    FeatureRating(
        "Sites",
        "Operator dashboard",
        7.5,
        "solid",
        "Dedicated health-center UI summarizes sites, API coverage, release trust, node metrics, and alerts.",
        "Add live log tail and backup restore drills.",
    ),
    FeatureRating(
        "Sites",
        "Exchange dashboard",
        7.0,
        "solid",
        "Dedicated custody UI explains deposit/withdrawal states and reserve readiness.",
        "Connect to live deposit/withdrawal tables.",
    ),
    FeatureRating(
        "Sites",
        "Wallet UI",
        7.5,
        "solid",
        "Browser wallet has profile unlock, recovery, private-key sign-in, address-type balances, PSBT/QR tools, and cleaner shell without the extra safety panel.",
        "Build the account switcher and persist send-review approvals.",
    ),
    FeatureRating(
        "Sites",
        "Accessibility",
        7.0,
        "improving",
        "Cleaner semantics and site audit coverage exist, but a full automated a11y matrix is still pending.",
        "Add axe/Playwright accessibility checks.",
    ),
    # Markets/exchange/ops
    FeatureRating(
        "Markets",
        "CLOB prediction markets",
        7.0,
        "solid",
        "Orderbook, order types, ticker, trades, and portfolio exist.",
        "Stress test matching engine and settlement.",
    ),
    FeatureRating(
        "Markets",
        "Oracle/evidence/disputes",
        7.0,
        "solid",
        "Evidence registry, oracle votes, dispute timeline, and integrity checks exist.",
        "Add resolver/reputation UI.",
    ),
    FeatureRating(
        "Markets",
        "Settlement reconciliation",
        7.0,
        "solid",
        "Settlement audit and reconciliation helpers exist.",
        "End-to-end settlement tests with edge cases.",
    ),
    FeatureRating(
        "Markets",
        "Market-maker tools",
        7.0,
        "improving",
        "Quote planning and risk helpers exist.",
        "Add dry-run bot dashboard.",
    ),
    FeatureRating(
        "Mining",
        "Stratum-lite pool",
        8.0,
        "strong",
        "TCP getwork/submit pool validates shares, accepts mined blocks, tracks per-miner accounting, creates payout plans, exposes CLI flags, and passes localnet probe tests.",
        "Add pooled payout transaction construction and longer multi-miner soak.",
    ),
    FeatureRating(
        "Exchange",
        "Deposit/withdrawal states",
        6.5,
        "improving",
        "Exchange state machines and accounting exist.",
        "Reorg-backed integration against live node.",
    ),
    FeatureRating(
        "Exchange",
        "Proof of reserves",
        7.0,
        "solid",
        "Merkle liabilities and attestation tools exist.",
        "Public verification page.",
    ),
    FeatureRating(
        "Exchange",
        "Production custody",
        6.2,
        "improving",
        "Hot/cold custody accounts, approval thresholds, hot-wallet coverage, and cold-to-hot transfer tracking exist.",
        "Connect to real cold signer and operator dashboard.",
    ),
    FeatureRating(
        "Faucet",
        "Faucet hardening",
        8.0,
        "strong",
        "Proof-of-work challenge, autoscaling difficulty, reputation scoring, device hints, daily cap, abuse summary, admin audit log, and CAPTCHA hooks exist.",
        "Add hosted CAPTCHA provider keys; CAPTCHA itself remains ops-secret capped.",
    ),
    FeatureRating(
        "Faucet",
        "Devnet + programmatic faucet",
        7.5,
        "solid",
        "`netcoin devnet --funded N` builds a mature-balance local chain in ~1.5s; POST /api/claim enforces a per-key rolling-24h quota via NETCOIN_FAUCET_API_KEYS.",
        "Add a hosted multi-tenant key-issuance flow instead of one shared env var.",
    ),
    # Developer API (game-studio / app-layer integration surface)
    FeatureRating(
        "Developer API",
        "Rewards API",
        7.0,
        "solid",
        "POST /developer/rewards records a reward, queues a signed webhook event, and returns an unsigned payout plan for wallet review. Real handler, tested.",
        "Add per-reward-reason analytics so a studio can see spend by event type.",
    ),
    FeatureRating(
        "Developer API",
        "Batch rewards API",
        6.5,
        "improving",
        "POST /developer/rewards/batch shares the same payout-plan and funding-policy path as single rewards, but has thinner standalone test coverage.",
        "Add large-batch (1000+) performance and partial-failure tests.",
    ),
    FeatureRating(
        "Developer API",
        "Withdrawal API",
        7.0,
        "solid",
        "POST /developer/withdrawals mirrors the reward path: unsigned payout plan only, nothing auto-broadcasts.",
        "Add withdrawal-specific webhook lifecycle events (requested/approved/paid).",
    ),
    FeatureRating(
        "Developer API",
        "Developer funding-policy (spend limits)",
        7.0,
        "solid",
        "Per-developer_id daily cap, per-user cap, payout-address allowlist, and pause flag enforced before rewards/withdrawals/batch rewards write state; derived from actual reward/withdrawal records, not a separate drift-prone counter. 7 tests.",
        "Add an admin UI for configuring the policy instead of raw POST /developer/funding-policy.",
    ),
    FeatureRating(
        "Developer API",
        "Payment Links",
        7.0,
        "solid",
        "POST /developer/payment-links creates a real invoice and checkout_url; pay.netcoin.online now renders it as a real hosted checkout view (amount, address, memo, offline-generated QR, wallet deep-link, and live polling) instead of requiring manual invoice lookup.",
        "Add a real Playwright E2E for the paid/confirmed transition, not just the unpaid render.",
    ),
    FeatureRating(
        "Developer API",
        "Webhooks (register/queue/deliver)",
        7.5,
        "solid",
        "Real HMAC-SHA256 signed delivery over raw JSON body with exponential backoff, a per-hook max_attempts budget, and a verifier snippet at /developer/webhook-verifiers. GET /developer/webhook-events/dead-letters now lists exhausted deliveries with their full attempt history (not just a bare count), and POST /developer/webhook-events/deliver takes an event_id to retry one specific delivery without touching everything else pending.",
        "Build an actual dashboard page for this instead of raw JSON — the data is there now, the UI isn't.",
    ),
    FeatureRating(
        "Developer API",
        "Watch-addresses / deposit detection",
        7.0,
        "solid",
        "GET /developer/deposits scans real chain UTXO data for registered addresses, and now queues a deposit.detected webhook the first time each confirmed deposit is seen (tracked per-watch via notified_txids so it never re-fires on repeated polls) — a caller registered for that event no longer has to poll to find out a deposit landed.",
        "Trigger the scan from block-connect instead of only on GET /developer/deposits reads, so it works even if nobody polls at all.",
    ),
    FeatureRating(
        "Developer API",
        "Idempotency keys",
        7.0,
        "solid",
        "Idempotency-Key header or JSON field dedupes reward/withdrawal writes, length-capped, tested.",
        "Document the dedupe TTL/retention policy explicitly.",
    ),
    FeatureRating(
        "Developer API",
        "Unsigned transaction builder / reward simulation",
        6.5,
        "improving",
        "POST /developer/transactions/build and /developer/simulate/rewards are real and give dust-risk guidance, but have narrower test coverage than the core reward/withdrawal paths.",
        "Add simulate-then-build round-trip tests.",
    ),
    FeatureRating(
        "Developer API",
        "Developer dashboard/console",
        6.0,
        "basic",
        "GET /developer/dashboard and /developer/console return real aggregated JSON, but there is no dedicated HTML console UI — a developer reads raw JSON today.",
        "Build a real sites/developers console page instead of JSON-only.",
    ),
    FeatureRating(
        "Developer API",
        "SDK packages advertisement",
        6.5,
        "improving",
        "sdk/netcoin-developer is now a real JS package wrapping every /developer/* endpoint (rewards, batch rewards, withdrawals, funding-policy, payment links, webhooks, watch-addresses, tx builder, simulation) plus HMAC webhook verification; GET /developer/sdk marks it status: real with an installable github: URL. Python and Unity are honestly marked status: planned with no install line instead of a fake one.",
        "Publish the JS package to npm for real (currently install-from-git only) and build the Python package next.",
    ),
    # Prediction markets (source-imported auto-resolution)
    FeatureRating(
        "Markets",
        "Polymarket-style import + auto-resolution queue",
        7.5,
        "solid",
        "Imported markets carry a close_time-based queue that transitions queued -> awaiting_source_result -> resolved, settling through the same payout/collateral-release/order-cancel path as a manual operator resolve. POST /markets/<id>/sync-source (and the bulk /markets/auto-resolution/sync + tools/sync_market_auto_resolution.py cron script) now actually polls the live Polymarket Gamma API for the real winner instead of requiring a human to type in source_winning_outcome_label.",
        "Wire the cron script into a real deploy (systemd timer) instead of leaving it a manual/on-demand call.",
    ),
    # Esplora-compatible API
    FeatureRating(
        "Node/API",
        "Esplora-compatible API",
        7.5,
        "solid",
        "netcoin/esplora.py + /esplora/* routes let Blockstream/BDK-family tooling point at NetCoin with just a URL change; tested against a real mined chain.",
        "Cover the less-common Esplora endpoints (fee histogram, mempool projection) for full parity.",
    ),
    # Verification / chaos tooling
    FeatureRating(
        "Node/API",
        "Localnet harness + chaos drill",
        7.0,
        "solid",
        "tools/run_localnet.py runs real multi-node subprocesses with dynamic ports for mining/relay/PEX/compact-block/restart-replay assertions; tools/run_chaos_drill.py adds hard-kill restart, corrupted-mempool recovery, dead-peer drain, and partition/rejoin with real competing-tip evidence.",
        "Run both on a scheduled CI cadence instead of on-demand only.",
    ),
    # Site information architecture
    FeatureRating(
        "Sites",
        "Navigation IA (Core tabs + Ecosystem)",
        8.0,
        "strong",
        "Explorer/Download/Home/Markets/Wallet render as flat always-visible tabs; Network/Build/Ecosystem are click-to-reveal category tabs with their own sub-tab row — no catch-all 'More' bucket. Redundant subdomains (treasury, network, keys) were retired to redirects into governance/nodes/security rather than left as dead duplicate content.",
        "Add analytics on which category tab gets used least to validate the grouping.",
    ),
)

_TOP_FIXES: tuple[dict[str, Any], ...] = (
    {
        "rank": 1,
        "area": "Protocol",
        "fix": "Completed: docs/spec now anchors consensus, policy, P2P, API, code paths, and parity-vector references.",
        "impact": "Protocol spec 2 -> 8",
    },
    {
        "rank": 2,
        "area": "Network",
        "fix": "Completed: bandwidth enforcement, DNS seeder, Stratum-lite pool, rate limiting, and node installer smoke coverage are real.",
        "impact": "Network/P2P package set 4-6 -> 6-8",
    },
    {
        "rank": 3,
        "area": "API/SDK",
        "fix": "Completed: /v1 aliases, OpenAPI source checker, Python/JS SDK smoke tests, and Rust SDK crate coverage.",
        "impact": "Versioned API/SDK 4-6 -> 8",
    },
    {
        "rank": 4,
        "area": "Product surfaces",
        "fix": "Completed: explorer pagination/CSV/reorg watch, faucet autoscaling/admin audit, status uptime history, Prometheus docs, and Grafana dashboard.",
        "impact": "Explorer/Faucet/Status metrics 5-7 -> 8",
    },
    {
        "rank": 5,
        "area": "Release/testing",
        "fix": "Completed: performance benchmark tool and CI workflow with regression thresholds.",
        "impact": "Perf evidence 2 -> 8",
    },
    {
        "rank": 6,
        "area": "Activation safety",
        "fix": "Completed: testnet-only versionbits rehearsal and genesis rehearsal both hard-refuse mainnet wiring.",
        "impact": "Versionbits/genesis rehearsal 1-2 -> 7-8",
    },
    {
        "rank": 7,
        "area": "Wallet",
        "fix": "Completed: private-key sign-in already exists; next make it a first-class account/profile switcher.",
        "impact": "Wallet UI 7 -> 7.5 now, 8 with account UX",
    },
    {
        "rank": 8,
        "area": "Sites",
        "fix": "Completed: 24-site shell sync, cache-busted shared shell, clean site audit, and searchable feature catalog.",
        "impact": "Sites/discoverability 8 -> 8.3",
    },
    {
        "rank": 9,
        "area": "Custody/markets",
        "fix": "Exchange custody and markets remain useful testnet demos; next jump requires live accounting tables, settlement soak, and resolver reputation UI.",
        "impact": "Exchange/markets mostly 6.5-7",
    },
    {
        "rank": 10,
        "area": "Quality",
        "fix": "Remaining honest blockers are external audit, long-running fuzz/soak history, independent DNS/ops, CAPTCHA secrets, and physical hardware-wallet transcripts.",
        "impact": "Caps several areas below professional 9-10",
    },
)


def all_features() -> list[dict[str, Any]]:
    return [asdict(f) for f in _FEATURES]


def grouped_features() -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for feature in all_features():
        groups.setdefault(feature["category"], []).append(feature)
    return groups


def rating_summary() -> dict[str, Any]:
    groups = grouped_features()
    by_category = []
    for category, items in groups.items():
        by_category.append(
            {
                "category": category,
                "count": len(items),
                "average_rating": round(mean(float(i["rating"]) for i in items), 2),
            }
        )
    ratings = [float(f.rating) for f in _FEATURES]
    return {
        "feature_count": len(_FEATURES),
        "average_rating": round(mean(ratings), 2),
        "strong_count": sum(1 for r in ratings if r >= 7),
        "weak_count": sum(1 for r in ratings if r < 6),
        "by_category": by_category,
    }


def top_impact_fixes() -> list[dict[str, Any]]:
    return [dict(item) for item in _TOP_FIXES]


def feature_catalog() -> dict[str, Any]:
    return {
        "schema": "netcoin-feature-catalog-v1",
        "scale": "1 skeletal, 5 usable testnet/demo, 7 strong, 10 audited/professional",
        "summary": rating_summary(),
        "groups": grouped_features(),
        "top_impact_fixes": top_impact_fixes(),
    }
