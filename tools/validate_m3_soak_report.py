#!/usr/bin/env python3
"""Validate M3 30-day public soak evidence without inventing evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED = [
    "duration_days",
    "independent_operator_count",
    "public_node_count",
    "non_founder_mined_block_hash",
    "block_propagation_p50_ms",
    "block_propagation_p99_ms",
    "orphan_rate",
    "mempool_depth_p99",
    "incident_links",
]


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    issues = []
    for key in REQUIRED:
        if key not in payload:
            issues.append(f"missing {key}")
    if float(payload.get("duration_days") or 0) < 30:
        issues.append("duration_days must be at least 30")
    if int(payload.get("independent_operator_count") or 0) < 10:
        issues.append("independent_operator_count must be at least 10")
    if int(payload.get("public_node_count") or 0) < 10:
        issues.append("public_node_count must be at least 10")
    if not str(payload.get("non_founder_mined_block_hash") or "").strip():
        issues.append("non_founder_mined_block_hash is required")
    if payload.get("hidden_incidents") is True:
        issues.append("hidden incidents are not allowed")
    return {"ok": not issues, "schema": "netcoin-m3-soak-evidence-check-v1", "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", nargs="?", default="reports/m3_evidence/soak_30_day_report.json")
    parser.add_argument("--out", default="reports/m3_soak_validation_report.json")
    args = parser.parse_args()
    path = Path(args.evidence)
    if not path.exists():
        result = {"ok": False, "schema": "netcoin-m3-soak-evidence-check-v1", "issues": [f"missing {args.evidence}"]}
    else:
        result = validate(json.loads(path.read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
