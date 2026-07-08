#!/usr/bin/env python3
"""Structural TypeScript workspace check without requiring npm install."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "api/package.json",
    "api/tsconfig.json",
    "api/src/index.ts",
    "api/src/schemas.ts",
    "api/src/client.ts",
    "api/src/migration-status.ts",
    "api/src/parity.ts",
    "api/src/parity-executor.ts",
    "web/package.json",
    "web/tsconfig.json",
]
REQUIRED_SYMBOLS = {
    "api/src/schemas.ts": [
        "SignedEnvelopeSchema",
        "MarketOrderSchema",
        "MigrationStatusSchema",
        "ParityStatusSchema",
        "WalletPreviewSchema",
        "ParityVectorSchema",
    ],
    "api/src/client.ts": [
        "NetCoinClient",
        "migrationStatus",
        "explorerAddress",
        "parityStatus",
        "parityVectors",
        "migrationReadiness",
    ],
    "api/src/migration-status.ts": ["migrationLanes", "summarizeMigration"],
    "api/src/parity.ts": ["ParityStatusSchema", "summarizeParity"],
    "api/src/parity-executor.ts": ["moneyInRange", "walletDecision", "orderNotionalOk"],
}


def main() -> int:
    issues = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            issues.append(f"missing {rel}")
    for rel, symbols in REQUIRED_SYMBOLS.items():
        text = (ROOT / rel).read_text(encoding="utf-8") if (ROOT / rel).exists() else ""
        for symbol in symbols:
            if symbol not in text:
                issues.append(f"{rel} missing symbol {symbol}")
    result = {"ok": not issues, "checked_files": len(REQUIRED), "issues": issues}
    print(json.dumps(result, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
