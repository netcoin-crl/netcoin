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
    "core-rs/crates/node/src/lib.rs",
    "core-rs/crates/wallet-core/src/lib.rs",
    "core-rs/crates/markets-core/src/lib.rs",
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
    ],
    "core-rs/crates/node/src/lib.rs": ["PeerSnapshot", "best_peer"],
    "core-rs/crates/wallet-core/src/lib.rs": [
        "WalletPreview",
        "RiskDecision",
        "decision_from_parts",
        "WalletPolicyPreview",
        "policy_decision",
    ],
    "core-rs/crates/markets-core/src/lib.rs": [
        "Quote",
        "settlement_conserves_value",
        "quote_from_bps",
        "fee_within_cap",
        "order_notional_ok",
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
