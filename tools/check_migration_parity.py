#!/usr/bin/env python3
"""Validate the NetCoin cross-language migration scaffold and parity vector map."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.migration_status import final_version_readiness, migration_status, parity_vectors
from netcoin.parity_suite import run_parity_suite


def main() -> int:
    status = migration_status(ROOT)
    vectors = parity_vectors(ROOT)
    readiness = final_version_readiness(ROOT)
    parity = run_parity_suite(ROOT)
    consensus = vectors.get("consensus", {})
    issues = []
    if not status["ok"]:
        issues.extend(f"missing required file: {path}" for path in status["missing"])
    if consensus.get("valid_cases", 0) <= 0:
        issues.append("consensus parity vectors must include at least one valid case")
    if consensus.get("invalid_cases", 0) <= 0:
        issues.append("consensus parity vectors must include at least one invalid case")
    if not status.get("vector_fingerprint"):
        issues.append("vector fingerprint missing")
    if not parity.get("ok"):
        issues.append("executable parity suite is not green")
    result = {
        "ok": not issues,
        "version": status["version"],
        "target_runtime": status["target_runtime"],
        "lane_count": len(status["lanes"]),
        "vector_fingerprint": status["vector_fingerprint"],
        "final_readiness": readiness,
        "parity": {"ok": parity["ok"], "total": parity["total"], "failed": parity["failed"]},
        "issues": issues,
    }
    print(json.dumps(result, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
