#!/usr/bin/env python3
"""Source and strict-evidence gate for M5 mainnet launch readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "m5-mainnet-launch.json"

TOKEN_CHECKS: dict[str, dict[str, list[str]]] = {
    "t-minus-four-feature-freeze": {
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md": ["T-4 weeks: feature freeze", "reports/m5_evidence/feature_freeze.json"],
        "docs/M5_LAUNCH_FREEZE_POLICY.md": [
            "Consensus changes without NIP/signoff",
            "reports/m5_evidence/feature_freeze.json",
        ],
    },
    "t-minus-three-public-announcement": {
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md": [
            "T-3 weeks: public launch announcement",
            "reports/m5_evidence/public_announcement.json",
        ],
        "docs/M5_LAUNCH_COMMUNICATIONS.md": ["NetCoin is preparing for mainnet launch", "Do **not** use"],
    },
    "t-minus-two-third-party-genesis-review": {
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md": [
            "T-2 weeks: third-party genesis review",
            "reports/m5_evidence/third_party_genesis_review.json",
        ],
        "config/mainnet_launch_plan.example.json": [
            "third-party genesis review missing or negative",
            "draft-only-not-approved-launch",
        ],
    },
    "t-minus-one-signed-binaries-and-pools": {
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md": [
            "T-1 week: signed binaries",
            "reports/m5_evidence/signed_binaries.json",
            "reports/m5_evidence/mining_pool_acknowledgements.json",
        ],
        "config/mainnet_launch_plan.example.json": [
            "signed release checksums",
            "less than 5 independent miners acknowledged",
        ],
    },
    "t-zero-genesis-ceremony": {
        "docs/M5_GENESIS_CEREMONY.md": [
            "blocked until M4 strict evidence",
            "does not mine genesis",
            "reports/m5_evidence/genesis_ceremony.json",
        ],
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md": ["T-0: genesis ceremony", "Launch is halted if any hash mismatch occurs"],
    },
    "t-plus-one-hundred-blocks-miner-diversity": {
        "docs/M5_POST_LAUNCH_MONITORING.md": ["100+ blocks observed", "5+ independent miners observed"],
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md": ["100+ blocks confirmed", "5+ independent miners observed"],
    },
    "t-plus-seven-independent-state-confirmation": {
        "docs/M5_POST_LAUNCH_MONITORING.md": [
            "Independent operator confirms chain state",
            "reports/m5_evidence/t_plus_7_state_confirmation.json",
        ],
    },
    "t-plus-thirty-no-emergency-hardfork": {
        "docs/M5_POST_LAUNCH_MONITORING.md": [
            "No unplanned hard fork required",
            "reports/m5_evidence/t_plus_30_stability.json",
        ],
    },
    "launch-oncall-incident-log": {
        "docs/M5_ONCALL_AND_INCIDENT_LOG.md": [
            "24/7 coverage for launch week",
            "reports/m5_evidence/oncall_rotation.json",
            "reports/m5_evidence/incident_log.json",
        ],
        "docs/M5_POST_LAUNCH_MONITORING.md": ["public incident log", "All major incidents disclosed"],
    },
    "launch-rollback-and-halt-policy": {
        "docs/M5_ROLLBACK_AND_HALT_POLICY.md": [
            "Halt before genesis",
            "Do not silently rewrite history",
            "public incident entry",
        ],
        "config/mainnet_launch_plan.example.json": ["halt_conditions", "incident owner/on-call rotation missing"],
    },
}

SOURCE_COMMANDS = [
    "python3 tools/check_m5_readiness.py --out reports/m5_readiness_source_report.json",
    "python3 tools/validate_m5_launch_plan.py --out reports/m5_mainnet_launch_plan_source_report.json",
    "python3 -m pytest tests/test_m5_mainnet_launch.py -q",
    "python3 -m py_compile tools/check_m5_readiness.py tools/run_m5_release_candidate.py tools/validate_m5_launch_plan.py tests/test_m5_mainnet_launch.py",
]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def _load_manifest() -> tuple[dict[str, Any], list[str]]:
    if not MANIFEST.exists():
        return {}, ["missing architecture/m5-mainnet-launch.json"]
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    issues: list[str] = []
    if payload.get("milestone") != "M5":
        issues.append("manifest milestone must be M5")
    if "cannot be fabricated" not in payload.get("claim_policy", ""):
        issues.append("manifest claim_policy must forbid fabricated launch evidence")
    hard_rules = "\n".join(str(item) for item in payload.get("hard_rules", []))
    for token in ["No genesis block", "No consensus", "No seed deployment", "M4 strict evidence"]:
        if token not in hard_rules:
            issues.append(f"manifest hard_rules missing token: {token}")
    ids = {item.get("id") for item in payload.get("deliverables", []) if isinstance(item, dict)}
    missing = sorted(set(TOKEN_CHECKS) - ids)
    if missing:
        issues.append("missing M5 deliverables: " + ", ".join(missing))
    return payload, issues


def source_gate() -> dict[str, Any]:
    manifest, issues = _load_manifest()
    results = []
    for gate_id, files in TOKEN_CHECKS.items():
        gate_issues: list[str] = []
        for rel, tokens in files.items():
            path = ROOT / rel
            if not path.exists():
                gate_issues.append(f"missing {rel}")
                continue
            text = _read(rel)
            for token in tokens:
                if token not in text:
                    gate_issues.append(f"{rel} missing token: {token}")
        results.append({"id": gate_id, "ok": not gate_issues, "issues": gate_issues})
        issues.extend(f"{gate_id}: {issue}" for issue in gate_issues)
    return {
        "ok": not issues,
        "milestone": "M5",
        "mode": "source",
        "claim_level": "m5-source-complete-evidence-required" if not issues else "m5-source-incomplete",
        "deliverable_count": len(TOKEN_CHECKS),
        "pass_count": len([item for item in results if item["ok"]]),
        "blocker_count": len([item for item in results if not item["ok"]]),
        "results": results,
        "issues": issues,
        "cannot_claim_mainnet_launched_without_strict_evidence": True,
        "no_genesis_or_seed_deployment_by_this_gate": True,
        "manifest_schema": manifest.get("schema"),
        "strict_evidence": manifest.get("strict_evidence", {}),
    }


def strict_gate() -> dict[str, Any]:
    result = source_gate()
    evidence = dict(result.get("strict_evidence", {}))
    evidence_issues: list[str] = []
    for _label, rel in evidence.items():
        path = ROOT / str(rel)
        if not path.exists():
            evidence_issues.append(f"missing strict evidence: {rel}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            evidence_issues.append(f"invalid JSON evidence {rel}: {exc}")
            continue
        if payload.get("ok") is not True:
            evidence_issues.append(f"strict evidence {rel} ok must be true")
    result["mode"] = "strict"
    result["issues"] = list(result.get("issues", [])) + evidence_issues
    result["ok"] = not result["issues"]
    result["claim_level"] = "m5-mainnet-launched" if result["ok"] else "m5-strict-evidence-required"
    result["blocker_count"] = len(result["issues"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="reports/m5_readiness_source_report.json")
    args = parser.parse_args()
    result = strict_gate() if args.strict else source_gate()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
