#!/usr/bin/env python3
"""Structural Rust workspace check used when cargo is not installed in CI/sandbox."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "core-rs/Cargo.toml",
    "core-rs/crates/consensus/Cargo.toml",
    "core-rs/crates/consensus/src/lib.rs",
    "core-rs/crates/consensus/src/bin/netcoin-consensus-parity.rs",
    "core-rs/crates/node/src/lib.rs",
    "core-rs/crates/mempool-core/Cargo.toml",
    "core-rs/crates/mempool-core/src/lib.rs",
    "core-rs/crates/mempool-core/src/bin/netcoin-mempool-parity.rs",
    "core-rs/crates/wallet-core/src/lib.rs",
    "core-rs/crates/wallet-core/src/bin/netcoin-wallet-parity.rs",
    "core-rs/crates/markets-core/src/lib.rs",
    "core-rs/crates/markets-core/src/bin/netcoin-markets-parity.rs",
    "core-rs/crates/signer-core/Cargo.toml",
    "core-rs/crates/signer-core/src/lib.rs",
    "core-rs/crates/signer-core/src/bin/netcoin-signer-parity.rs",
    "core-rs/crates/node/src/bin/netcoin-p2p-parity.rs",
    "core-rs/crates/indexer-core/Cargo.toml",
    "core-rs/crates/indexer-core/src/lib.rs",
    "core-rs/crates/indexer-core/src/bin/netcoin-indexer-parity.rs",
    "core-rs/fixtures/parity-vectors.json",
]
REQUIRED_SYMBOLS = {
    "core-rs/crates/consensus/src/lib.rs": [
        "ConsensusVectorSummary",
        "double_sha256_hex",
        "validate_linked_headers",
        "block_weight_ok",
        "checkpoint_ok",
        "tx_fee_ok",
        "merkle_root_hex",
        "subsidy_at_height",
        "run_consensus_case",
        "run_consensus_parity_vectors",
    ],
    "core-rs/crates/consensus/src/bin/netcoin-consensus-parity.rs": [
        "run_consensus_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
    "core-rs/crates/node/src/lib.rs": [
        "PeerSnapshot",
        "best_peer",
        "p2p_best_peer_summary",
        "p2p_header_sync_summary",
        "p2p_ban_score_summary",
        "run_p2p_case",
        "run_p2p_parity_vectors",
    ],
    "core-rs/crates/node/src/bin/netcoin-p2p-parity.rs": [
        "run_p2p_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
    "core-rs/crates/mempool-core/src/lib.rs": [
        "MempoolPolicySummary",
        "mempool_fee_rate_sat_vb",
        "mempool_policy_summary",
        "mempool_ordering_summary",
        "run_mempool_case",
        "run_mempool_parity_vectors",
    ],
    "core-rs/crates/mempool-core/src/bin/netcoin-mempool-parity.rs": [
        "run_mempool_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
    "core-rs/crates/wallet-core/src/lib.rs": [
        "WalletPreview",
        "RiskDecision",
        "decision_from_parts",
        "WalletPolicyPreview",
        "policy_decision",
        "wallet_decision",
        "wallet_policy_summary",
        "run_wallet_case",
        "run_wallet_parity_vectors",
    ],
    "core-rs/crates/wallet-core/src/bin/netcoin-wallet-parity.rs": [
        "run_wallet_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
    "core-rs/crates/markets-core/src/lib.rs": [
        "Quote",
        "settlement_conserves_value",
        "quote_from_bps",
        "fee_within_cap",
        "order_notional_ok",
        "price_tick_ok",
        "collateral_ok",
        "order_crosses",
        "lifecycle_allows_order",
        "settlement_state_ok",
        "portfolio_conserves",
        "run_market_case",
        "run_markets_parity_vectors",
    ],
    "core-rs/crates/markets-core/src/bin/netcoin-markets-parity.rs": [
        "run_markets_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
    "core-rs/crates/signer-core/src/lib.rs": [
        "signer_digest",
        "signer_policy_summary",
        "signer_envelope_summary",
        "run_signer_case",
        "run_signer_parity_vectors",
    ],
    "core-rs/crates/signer-core/src/bin/netcoin-signer-parity.rs": [
        "run_signer_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
    "core-rs/crates/indexer-core/src/lib.rs": [
        "indexer_address_summary",
        "indexer_reorg_summary",
        "indexer_market_event_summary",
        "indexer_snapshot_hash",
        "run_indexer_case",
        "run_indexer_parity_vectors",
    ],
    "core-rs/crates/indexer-core/src/bin/netcoin-indexer-parity.rs": [
        "run_indexer_parity_vectors",
        "serde_json::to_string_pretty",
        "process::exit",
    ],
}


def main() -> int:
    issues = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            issues.append(f"missing {rel}")
    for rel, symbols in REQUIRED_SYMBOLS.items():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for symbol in symbols:
            if symbol not in text:
                issues.append(f"{rel} missing symbol {symbol}")
    result = {"ok": not issues, "checked_files": len(REQUIRED), "issues": issues}
    print(json.dumps(result, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
