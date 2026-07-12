#!/usr/bin/env python3
"""Validate the M5 mainnet launch-plan template.

This validator intentionally does not mine genesis, approve launch, or touch live
infrastructure. It only checks that the launch plan is a draft with the right
halt conditions and evidence expectations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "mainnet_launch_plan.example.json"

REQUIRED_WINDOWS = {
    "t_minus_4_weeks",
    "t_minus_3_weeks",
    "t_minus_2_weeks",
    "t_minus_1_week",
    "t_zero",
    "t_plus_1_day",
    "t_plus_7_days",
    "t_plus_30_days",
}

REQUIRED_HALT_TOKENS = [
    "M4 strict evidence missing",
    "external audit critical/high unresolved",
    "genesis distribution approval missing",
    "legal posture missing",
    "less than 10 independent node operators ready",
    "less than 5 independent miners acknowledged",
    "release signing verification fails",
    "third-party genesis review missing or negative",
    "incident owner/on-call rotation missing",
]


def validate() -> dict[str, Any]:
    issues: list[str] = []
    if not PLAN.exists():
        return {
            "ok": False,
            "claim_level": "m5-launch-plan-missing",
            "issues": ["missing config/mainnet_launch_plan.example.json"],
        }
    payload = json.loads(PLAN.read_text(encoding="utf-8"))
    if payload.get("schema") != "netcoin-mainnet-launch-plan-draft-v1":
        issues.append("launch plan schema must be netcoin-mainnet-launch-plan-draft-v1")
    if payload.get("status") != "draft-only-not-approved-launch":
        issues.append("launch plan status must be draft-only-not-approved-launch")
    if payload.get("does_not_mine_genesis") is not True:
        issues.append("launch plan must explicitly not mine genesis")
    if payload.get("requires_m4_strict_completion") is not True:
        issues.append("launch plan must require M4 strict completion")
    windows = set((payload.get("launch_window") or {}).keys())
    missing_windows = sorted(REQUIRED_WINDOWS - windows)
    if missing_windows:
        issues.append("launch plan missing windows: " + ", ".join(missing_windows))
    halt_text = "\n".join(str(item) for item in payload.get("halt_conditions", []))
    for token in REQUIRED_HALT_TOKENS:
        if token not in halt_text:
            issues.append(f"launch plan missing halt condition: {token}")
    approvals = set(payload.get("required_operator_approvals", []))
    for approval in ["release_manager", "security", "ops", "wallet", "custody", "legal_or_posture_owner"]:
        if approval not in approvals:
            issues.append(f"launch plan missing approval role: {approval}")
    return {
        "ok": not issues,
        "claim_level": "draft-only-not-approved-launch" if not issues else "m5-launch-plan-source-incomplete",
        "does_not_generate_or_mine_genesis": True,
        "requires_m4_strict_completion": payload.get("requires_m4_strict_completion") is True,
        "required_launch_windows": sorted(REQUIRED_WINDOWS),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/m5_mainnet_launch_plan_source_report.json")
    args = parser.parse_args()
    result = validate()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
