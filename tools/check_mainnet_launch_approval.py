#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.mainnet_readiness import strict_evidence_gate

REQUIRED = [
    "release_manager_approval",
    "security_approval",
    "ops_approval",
    "wallet_approval",
    "custody_approval",
    "rollback_plan",
    "genesis_or_upgrade_hash",
]


def source_result() -> dict[str, object]:
    checklist = ROOT / "docs" / "PRE_MAINNET_SECURITY_CHECKLIST.md"
    launch = ROOT / "docs" / "PROFESSIONAL_LAUNCH_CHECKLIST.md"
    issues = []
    if not checklist.exists():
        issues.append("missing docs/PRE_MAINNET_SECURITY_CHECKLIST.md")
    if not launch.exists():
        issues.append("missing docs/PROFESSIONAL_LAUNCH_CHECKLIST.md")
    return {
        "gate_id": "mainnet-launch-checklist-approval",
        "ok": not issues,
        "mode": "source",
        "status": "source-complete-evidence-required" if not issues else "source-issues",
        "required_approvals": REQUIRED,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence", default="reports/mainnet_evidence/mainnet_launch_approval.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = (
        strict_evidence_gate("mainnet-launch-checklist-approval", ROOT / args.evidence, REQUIRED).to_dict()
        if args.strict
        else source_result()
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
