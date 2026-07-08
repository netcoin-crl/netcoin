"""Registry of competitive NetCoin feature scaffolds.

The registry intentionally separates *scaffolding exists* from *production
complete*. Each feature starts as ``scaffolded`` until real implementation,
independent audit, operational evidence, and legal/security review move it to a
higher status.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FeatureSkeleton:
    slug: str
    title: str
    status: str
    owner: str
    code_anchor: str
    doc_anchor: str
    config_anchor: str
    test_anchor: str
    acceptance_criteria: tuple[str, ...]


@dataclass(frozen=True)
class FeatureArea:
    slug: str
    title: str
    purpose: str
    module: str
    doc_path: str
    config_path: str
    test_path: str
    features: tuple[FeatureSkeleton, ...]


def _slugify(value: str) -> str:
    out = []
    prev_dash = False
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("_")
            prev_dash = True
    return "".join(out).strip("_")


def _feature(area_slug: str, module: str, title: str) -> FeatureSkeleton:
    slug = _slugify(title)
    return FeatureSkeleton(
        slug=slug,
        title=title,
        status="midlevel_testnet",
        owner="unassigned",
        code_anchor=f"netcoin/competitive/{module}.py::{slug}",
        doc_anchor=f"docs/competitive/{area_slug}.md#{slug.replace('_', '-')}",
        config_anchor=f"config/competitive/{area_slug}.json",
        test_anchor="tests/test_competitive_scaffold.py",
        acceptance_criteria=(
            "implementation exists behind a safe testnet/default-off gate",
            "unit and integration tests cover normal and failure paths",
            "operator documentation and rollback notes exist",
            "security review has no unresolved critical/high findings",
        ),
    )


_AREA_DATA: dict[str, dict[str, Any]] = {
    "security_audit": {
        "title": "Security Audit and Abuse Defense",
        "module": "security",
        "purpose": "External-audit readiness, disclosure, fuzzing, static analysis, penetration-testing, and abuse simulation scaffolds.",
        "features": [
            "External security audit intake and finding tracker",
            "Bug bounty scope and safe-harbor workflow",
            "Threat-model attack-tree registry",
            "Block/transaction/P2P/API fuzzing harness placeholders",
            "Static analysis and dependency/secret scanning gates",
            "Secrets inventory and rotation checklist",
            "Incident-response owner/escalation mapping",
            "Security advisory and patch-release workflow",
            "Penetration-test scope for explorer/API/admin/markets/faucet",
            "Abuse simulations for faucet, markets, spam, peers, and wallet phishing",
        ],
    },
    "consensus_chain": {
        "title": "Consensus and Chain Correctness",
        "module": "consensus",
        "purpose": "Consensus-critical specification, test vectors, reorg/fork handling, difficulty tests, and invalid-data corpus scaffolds.",
        "features": [
            "Complete consensus protocol specification map",
            "Expanded block/transaction/signature/difficulty test vectors",
            "Deep reorg handling matrix for wallet, explorer, and exchange deposits",
            "Fork-choice edge-case tests and activation rules",
            "Difficulty/timestamp/hash-rate stress-test plan",
            "Chain split detection and alert hooks",
            "Invalid block and transaction corpus registry",
            "Deterministic genesis regeneration workflow",
            "Consensus-code isolation boundary checklist",
        ],
    },
    "p2p_network": {
        "title": "Node and P2P Network Hardening",
        "module": "p2p",
        "purpose": "Peer scoring, banning, eclipse-resistance, discovery, relay efficiency, privacy transport, and node-map scaffolds.",
        "features": [
            "Peer scoring by latency, stale tips, invalid messages, and behavior",
            "Temporary and permanent peer banning policy",
            "Eclipse-attack peer diversity constraints",
            "DNS seed and fallback seed operations registry",
            "Address gossip freshness model",
            "Headers-first initial sync plan",
            "Compact block relay roadmap",
            "Bandwidth and message-rate limits",
            "Tor/I2P transport placeholders",
            "Public node map and version dashboard hooks",
            "Node upgrade and unsafe-version alerts",
        ],
    },
    "storage_sync_recovery": {
        "title": "Storage, Sync, and Recovery",
        "module": "storage",
        "purpose": "Reindexing, pruning, snapshots, crash-safe writes, migrations, backups, chain repair, and soak-test scaffolds.",
        "features": [
            "Reindex command plan for chainstate and explorer index",
            "Prune-mode capability map",
            "Snapshot/bootstrap import and verification workflow",
            "Crash-safe write and corruption-test matrix",
            "Versioned database migration registry",
            "Backup and restore tooling checklist",
            "Chainstate repair and audit hooks",
            "Long-run node soak-test plan",
        ],
    },
    "wallet_security_ux": {
        "title": "Wallet Security and Professional UX",
        "module": "wallet",
        "purpose": "Encrypted wallets, seed backup verification, auto-locking, hardware/watch-only/multisig/offline signing, risk warnings, and policy controls.",
        "features": [
            "Strong encrypted wallet file and migration policy",
            "Seed phrase backup verification requirement",
            "Auto-lock idle timeout model",
            "Hardware wallet signer interface placeholder",
            "Watch-only wallet workflow",
            "Multisig wallet creation/sign/combine/broadcast workflow",
            "Offline and QR-based signing flows",
            "Address book with labels and warnings",
            "Address reuse and address poisoning warnings",
            "Transaction simulation and risk scoring hooks",
            "Coin-control UI/API plan",
            "Spending limits and wallet policy rules",
        ],
    },
    "mempool_fees_spam": {
        "title": "Mempool, Fees, and Spam Resistance",
        "module": "mempool",
        "purpose": "Dynamic fees, relay policy, eviction, RBF/CPFP, dependency limits, dust/UTXO-bloat controls, and analytics.",
        "features": [
            "Dynamic fee estimation from mempool and recent blocks",
            "Minimum relay fee and spam-protection policy",
            "Mempool eviction for low-fee/stale/conflicting transactions",
            "Replace-by-fee transaction replacement plan",
            "Child-pays-for-parent fee bumping plan",
            "Ancestor and descendant dependency limits",
            "Dust rules and uneconomical output rejection",
            "UTXO bloat detection and discouragement",
            "Mempool fee histogram, size, age, and top transaction analytics",
        ],
    },
    "mining_pool": {
        "title": "Mining and Pool Infrastructure",
        "module": "mining",
        "purpose": "Stratum-style pool, miner dashboard, share tracking, payout accounting, orphan metrics, block templates, and profitability scaffolds.",
        "features": [
            "Stratum-style mining pool protocol adapter",
            "Mining pool dashboard data model",
            "Rejected share tracking and diagnostics",
            "Transparent pool payout accounting ledger",
            "Orphan/stale block-rate tracking",
            "Miner-friendly block template API",
            "Mining profitability calculator inputs",
            "Difficulty/hashrate explorer chart hooks",
        ],
    },
    "explorer_indexer": {
        "title": "Explorer and Indexer",
        "module": "explorer",
        "purpose": "Production indexer, address history, mempool explorer, charts, token/contract pages, API docs, rate limits, labels, and uptime hooks.",
        "features": [
            "Dedicated production indexer with DB migrations",
            "Rich address pages with balance history and transaction graph",
            "Mempool explorer for pending transactions and fee levels",
            "Supply/difficulty/block-time/fee/hashrate chart feeds",
            "Token/contract holder, event, and transfer pages",
            "Explorer OpenAPI docs and examples",
            "Explorer API rate-limit and abuse-detection policy",
            "Verified known-address labels",
            "Explorer uptime, latency, and error-rate metrics",
        ],
    },
    "faucet_abuse": {
        "title": "Faucet Abuse Control",
        "module": "faucet",
        "purpose": "Faucet anti-abuse dashboard, captcha/proof-of-work, fingerprinting, hot-wallet limits, alerts, queues, and emergency pause.",
        "features": [
            "Faucet abuse dashboard and anomaly counters",
            "Captcha or proof-of-work challenge adapter",
            "Device/IP/reputation fingerprinting hooks",
            "Faucet hot-wallet balance and daily spend limits",
            "Faucet refill and low-balance alerts",
            "Request queue analytics and decision logs",
            "Automatic emergency pause during abnormal activity",
            "Faucet user/request reputation scoring",
        ],
    },
    "api_app_layer": {
        "title": "App-Layer API Professionalization",
        "module": "api",
        "purpose": "Signed writes, replay/idempotency protection, scoped API keys, usage dashboards, webhooks, RBAC, audit logs, and OpenAPI scaffolds.",
        "features": [
            "Mandatory signed writes for sensitive endpoints",
            "Global nonce replay protection coverage map",
            "Global idempotency-key coverage map",
            "Scoped API key model for read/write/admin/market/faucet actions",
            "Per-key API usage dashboard and export",
            "Webhook HMAC signing and verification contract",
            "Webhook retry log and manual replay workflow",
            "Role-based admin permissions",
            "Immutable audit log for sensitive actions",
            "Complete OpenAPI schema and example set",
        ],
    },
    "prediction_markets": {
        "title": "Prediction-Market Integrity",
        "module": "markets",
        "purpose": "Play-money market integrity scaffolds: surveillance, disputes, oracles, liquidity controls, reputation, warnings, operators, reconciliation, and analytics.",
        "features": [
            "Real-money compliance gate that blocks production claims",
            "Manipulation surveillance for wash trading, spoofing, self-trades, and rapid moves",
            "Dispute timeline, evidence upload, appeal, and operator-role workflow",
            "Oracle/evidence trusted source registry and snapshot proof model",
            "Liquidity and exposure controls",
            "Market creator reputation model",
            "Jurisdiction-restriction placeholder for future legal review",
            "Responsible-use warnings across UI/API/docs",
            "Operator separation of duties for creator/resolver/auditor/admin roles",
            "Payout reconciliation accounting checks",
            "Market-maker/liquidity-bot tooling placeholder",
            "Historical probability, volume, and open-interest analytics",
        ],
    },
    "smart_contracts_tokens": {
        "title": "Smart Contracts and Tokens",
        "module": "contracts",
        "purpose": "Formal VM/execution model, gas metering, sandboxing, static analysis, source verification, events, upgrades, oracles, and token standards.",
        "features": [
            "Deterministic VM/execution-model design placeholder",
            "Gas/resource metering policy",
            "Contract sandboxing boundary",
            "Contract static analyzer rule registry",
            "Verified source registry and explorer integration plan",
            "Contract event log/indexing plan",
            "Contract upgrade and admin-safety policy",
            "Oracle design and risk registry",
            "Reentrancy/access-control/integer/randomness/DoS safety checklist",
            "Fungible and non-fungible token standards roadmap",
        ],
    },
    "governance_treasury": {
        "title": "Governance and Treasury",
        "module": "governance",
        "purpose": "Proposal lifecycle, voting rules, treasury multisig, public dashboard, spending audit trail, governance calendar, decision log, and emergency governance.",
        "features": [
            "Proposal lifecycle states and metadata",
            "On-chain/off-chain voting rules, quorum, periods, and snapshots",
            "Treasury multisig signer policy and rotation plan",
            "Public treasury dashboard feed",
            "Immutable spending audit trail",
            "Governance calendar and upgrade schedule",
            "Permanent decision log",
            "Emergency governance and critical-patch process",
        ],
    },
    "release_supply_chain": {
        "title": "Release Trust and Supply Chain",
        "module": "release",
        "purpose": "Reproducible builds, signatures, checksums, SBOM, attestations, dependency review, verification docs, and rollback plan.",
        "features": [
            "Deterministic/reproducible build verification in CI",
            "GPG/Sigstore signed release artifacts",
            "Automatic checksum generation and publishing",
            "SBOM generation and vulnerability-review gate",
            "Source-to-artifact provenance attestation",
            "Dependency lock and human review workflow",
            "Binary/source verification instructions for users",
            "Bad release rollback and revocation process",
        ],
    },
    "observability_ops": {
        "title": "Observability and Operations",
        "module": "observability",
        "purpose": "Prometheus/Grafana, public status, alerts, chain/faucet/API monitoring, backups, disaster recovery, and incident history.",
        "features": [
            "Prometheus metric namespace for node/explorer/faucet/market/API",
            "Grafana dashboard skeletons",
            "Public status page backed by live health data",
            "Slack/Discord/email/PagerDuty alert hooks",
            "Chain split and divergent-tip alerts",
            "Stuck block alerting",
            "API latency and error-rate alerting",
            "Backup completion monitoring",
            "Disaster recovery restore drills",
            "Public incident history feed",
        ],
    },
    "exchange_custody": {
        "title": "Exchange and Custody Readiness",
        "module": "exchange",
        "purpose": "Deposits, reorgs, withdrawals, hot/cold wallets, address validation, proof-of-reserves, fork alerts, exchange guide, and custody policy.",
        "features": [
            "Deposit confirmation policy by risk level",
            "Reorg handling for deposits and balance reconciliation",
            "Withdrawal queue, batching, approvals, and limits",
            "Hot/cold wallet separation architecture",
            "Exchange-safe address validation endpoint contract",
            "Proof-of-reserves guide and data model",
            "Chain halt/fork alerting for exchanges",
            "Exchange integration guide with API examples",
            "Custody key ceremony, signer roles, and access-control policy",
        ],
    },
    "developer_ecosystem": {
        "title": "Developer Ecosystem",
        "module": "developer",
        "purpose": "SDK coverage, OpenAPI, Postman, example apps, Docker devnet, CLI polish, webhooks, and public testnet status API.",
        "features": [
            "Typed JavaScript SDK coverage plan",
            "Full Python SDK endpoint coverage plan",
            "Machine-readable OpenAPI schema",
            "Postman collection generation placeholder",
            "Example wallet/faucet/market/explorer apps",
            "One-command Docker multi-node devnet",
            "CLI profile and error-polish checklist",
            "Signed webhook receiver examples",
            "Public testnet status API with chain/faucet health",
        ],
    },
    "product_trust": {
        "title": "Product, Website, and Trust",
        "module": "product",
        "purpose": "Roadmap, security/download pages, transparency, risk disclosures, legal disclaimers, changelog, FAQ, miner guide, and node-operator guide.",
        "features": [
            "Public roadmap with status and dates",
            "Security page with disclosure policy and audit status",
            "Download verification page for checksums/signatures",
            "Project transparency page for maintainers and governance roles",
            "Consistent testnet/educational/no-real-value risk disclosures",
            "Brand/legal disclaimer registry across public pages",
            "Public changelog grouped by release",
            "FAQ for wallet/mining/faucet/markets/safety/testnet",
            "Miner setup and troubleshooting guide",
            "Node operator install/upgrade/monitor/recover guide",
        ],
    },
    "testing_quality": {
        "title": "Testing, Quality, and Chaos Engineering",
        "module": "testing",
        "purpose": "Full CI, property tests, fuzzing, load/soak/chaos/browser/security/migration/release verification tests.",
        "features": [
            "Full test suite CI matrix with timeout budgets",
            "Property-based randomized consensus and wallet tests",
            "Parser and network fuzzing jobs",
            "Explorer/API/faucet/market load tests",
            "Long-running node soak tests",
            "Chaos tests for restarts, DB corruption, partitions, and bad peers",
            "Browser UI tests for wallet/explorer/markets",
            "Security regression tests for auth/replay/CSRF/rate limits",
            "Migration compatibility tests from old data formats",
            "Release verification workflow tests",
        ],
    },
}


def _build_areas() -> tuple[FeatureArea, ...]:
    built: list[FeatureArea] = []
    for area_slug, data in _AREA_DATA.items():
        module = data["module"]
        features = tuple(_feature(area_slug, module, title) for title in data["features"])
        built.append(
            FeatureArea(
                slug=area_slug,
                title=data["title"],
                purpose=data["purpose"],
                module=module,
                doc_path=f"docs/competitive/{area_slug}.md",
                config_path=f"config/competitive/{area_slug}.json",
                test_path="tests/test_competitive_scaffold.py",
                features=features,
            )
        )
    return tuple(built)


COMPETITIVE_AREAS = _build_areas()
COMPETITIVE_FEATURES = tuple(feature for area in COMPETITIVE_AREAS for feature in area.features)


def area_slugs() -> list[str]:
    return [area.slug for area in COMPETITIVE_AREAS]


def feature_count() -> int:
    return len(COMPETITIVE_FEATURES)


def get_area(slug: str) -> FeatureArea:
    for area in COMPETITIVE_AREAS:
        if area.slug == slug:
            return area
    raise KeyError(f"unknown competitive area: {slug}")


def build_competitive_gap_report() -> dict[str, Any]:
    areas = []
    for area in COMPETITIVE_AREAS:
        areas.append(
            {
                "slug": area.slug,
                "title": area.title,
                "purpose": area.purpose,
                "module": f"netcoin/competitive/{area.module}.py",
                "doc_path": area.doc_path,
                "config_path": area.config_path,
                "test_path": area.test_path,
                "feature_count": len(area.features),
                "features": [
                    dict(asdict(feature), maturity_score=5, production_ready=False) for feature in area.features
                ],
            }
        )
    return {
        "schema": "netcoin-competitive-scaffold-v1",
        "target_minimum_score": 5,
        "minimum_feature_score": 5,
        "production_claim": False,
        "warning": "These are 5/10 midlevel testnet implementations. They do not replace audits, legal review, or production operations.",
        "area_count": len(COMPETITIVE_AREAS),
        "feature_count": len(COMPETITIVE_FEATURES),
        "areas": areas,
    }
