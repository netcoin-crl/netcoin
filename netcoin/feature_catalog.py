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
        7.0,
        "solid",
        "Dedicated consensus module with activation-height design.",
        "Public deployment governance process.",
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
        7.0,
        "solid",
        "Local browser wallet with vault module and core flows.",
        "Full Playwright coverage and stronger vault UX.",
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
        7.8,
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
        6.5,
        "improving",
        "PeerManager, peerdb, scoring, bans, sync scheduler, and bad-header peer penalties exist.",
        "Integrate full binary block relay under soak tests.",
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
        7.0,
        "solid",
        "Metrics history, health summaries, incidents, and runbooks exist.",
        "Add Grafana dashboard fixtures.",
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
        8.0,
        "strong",
        "Sleek shared navigation and feature launcher across sites.",
        "Automated shell sync checks.",
    ),
    FeatureRating(
        "Sites",
        "Feature discoverability",
        8.0,
        "strong",
        "Global feature launcher exposes key tools.",
        "Add searchable full feature directory.",
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
        7.0,
        "solid",
        "Good explorer surface; indexer APIs exist.",
        "Wire rich indexer profiles into UI.",
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
        7.0,
        "solid",
        "Browser wallet and recovery shortcuts exist.",
        "Integrate approval queue and simulator UX.",
    ),
    FeatureRating(
        "Sites",
        "Accessibility",
        6.5,
        "improving",
        "Cleaner semantics but needs full a11y pass.",
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
        6.5,
        "improving",
        "Quote planning and risk helpers exist.",
        "Add dry-run bot dashboard.",
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
        7.5,
        "solid",
        "Proof-of-work challenge, reputation scoring, device hints, daily cap, abuse summary, and CAPTCHA hooks exist.",
        "Add hosted CAPTCHA provider keys and operator dashboard charts.",
    ),
)

_TOP_FIXES: tuple[dict[str, Any], ...] = (
    {
        "rank": 1,
        "area": "Community",
        "fix": "Completed: votes, comments, sorting, and moderation queue are real.",
        "impact": "Community 7 -> 8",
    },
    {
        "rank": 2,
        "area": "Sites",
        "fix": "Add searchable feature directory and /api/features catalog.",
        "impact": "Discoverability 8 -> 8.5",
    },
    {
        "rank": 3,
        "area": "Wallet",
        "fix": "Completed: send UI includes risk simulator; next persist risk reports into approval queue.",
        "impact": "Wallet 7 -> 8",
    },
    {
        "rank": 4,
        "area": "Explorer",
        "fix": "Completed: explorer quick cards expose mempool, latest blocks, address lookup, and operator health; next wire full indexer graphs.",
        "impact": "Explorer 7 -> 7.5",
    },
    {
        "rank": 5,
        "area": "P2P",
        "fix": "Completed: header scheduler validates linked segments and assigns via peerdb; next run adversarial soak.",
        "impact": "P2P 6 -> 7",
    },
    {
        "rank": 6,
        "area": "Exchange",
        "fix": "Completed: hot/cold custody accounts plus a dedicated exchange dashboard; next connect live accounting tables.",
        "impact": "Custody 4.5 -> 7",
    },
    {
        "rank": 7,
        "area": "Security",
        "fix": "Add Sigstore/GitHub attestation release verification in CI and UI.",
        "impact": "Release trust 7 -> 8",
    },
    {
        "rank": 8,
        "area": "Markets",
        "fix": "Stress-test matching/settlement and add resolver reputation UI.",
        "impact": "Markets 7 -> 8",
    },
    {
        "rank": 9,
        "area": "Faucet",
        "fix": "Completed: proof-of-work, reputation scoring, daily cap, and abuse summary; next add dashboard charts.",
        "impact": "Faucet 6.5 -> 7.5",
    },
    {
        "rank": 10,
        "area": "Quality",
        "fix": "Completed: product-surface checker, health-center API, browser E2E coverage, and full-suite report tool.",
        "impact": "Product reliability 7 -> 8",
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
