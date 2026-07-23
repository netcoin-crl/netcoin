#!/usr/bin/env python3
"""Source and strict-evidence gate for M4 mainnet readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "m4-mainnet-ready.json"

TOKEN_CHECKS = {
    "external-audit-register": {
        "docs/MAINNET_AUDIT_FINDINGS_REGISTER.md": [
            "critical/high",
            "reports/m4_evidence/external_audit_completion.json",
        ],
        "docs/AUDIT_SCOPING_PACKAGE.md": ["audit", "scope"],
    },
    "formal-spec-freeze": {
        "docs/PROTOCOL_SPEC.md": ["Block Header", "Transactions", "Mempool Policy"],
        "docs/MAINNET_PROTOCOL_SPEC_FREEZE.md": ["Frozen protocol spec hash", "parity fingerprint"],
    },
    "version-bits-checkpoint-signoff": {
        "docs/M4_VERSION_BITS_AND_CHECKPOINT_SIGNOFF.md": [
            "blocked-by-consensus-signoff",
            "explicit same-session user signoff",
            "NIP",
        ],
    },
    "genesis-distribution-manifest": {
        "docs/MAINNET_GENESIS_DISTRIBUTION_PROPOSAL.md": [
            "not an approved genesis allocation",
            "reports/m4_evidence/genesis_distribution_approval.json",
        ],
        "config/mainnet_distribution.example.json": [
            "netcoin-mainnet-distribution-draft-v1",
            "requires_public_approval",
        ],
        "tools/validate_mainnet_distribution.py": ["does_not_generate_genesis", "draft-only-not-approved-genesis"],
    },
    "testnet-migration-plan": {
        "docs/MAINNET_MIGRATION_PLAN.md": ["Snapshot height/date", "Users should not be forced to expose seed phrases"],
    },
    "cold-storage-multisig-runbook": {
        "docs/MAINNET_COLD_STORAGE_RUNBOOK.md": [
            "No single signer can move funds",
            "reports/m4_evidence/cold_storage_ceremony.json",
        ],
    },
    "performance-targets": {
        "docs/MAINNET_PERFORMANCE_TARGETS.md": ["< 500 ms", "< 200 MB", "< 10 GB/year"],
    },
    "nip-process-governance": {
        "docs/nips/NIP-0001.md": ["Draft", "Review", "Accepted", "Active"],
        "docs/MAINNET_GOVERNANCE_LEGAL_RUNBOOK.md": ["Genesis distribution NIP", "Foundation/entity"],
    },
    "legal-risk-posture": {
        "docs/MAINNET_GOVERNANCE_LEGAL_RUNBOOK.md": ["not legal advice", "MSB/FinCEN posture", "counsel review"],
    },
    "monetary-policy-publication": {
        "docs/MAINNET_MONETARY_POLICY.md": ["50 NET", "No hidden premine", "public NIP"],
    },
}

SOURCE_COMMANDS = [
    "python3 tools/check_m4_readiness.py --out reports/m4_readiness_source_report.json",
    "python3 tools/validate_mainnet_distribution.py --out reports/m4_mainnet_distribution_source_report.json",
    "python3 -m pytest tests/test_m4_mainnet_ready.py -q",
    "python3 -m py_compile tools/check_m4_readiness.py tools/run_m4_release_candidate.py tools/validate_mainnet_distribution.py tests/test_m4_mainnet_ready.py",
]

STRICT_EVIDENCE = {
    "external_audit": "reports/m4_evidence/external_audit_completion.json",
    "spec_freeze": "reports/m4_evidence/protocol_spec_freeze.json",
    "consensus_signoff": "reports/m4_evidence/consensus_change_signoff.json",
    "genesis_distribution": "reports/m4_evidence/genesis_distribution_approval.json",
    "legal_posture": "reports/m4_evidence/legal_posture_counsel_review.json",
    "foundation_entity": "reports/m4_evidence/foundation_or_entity.json",
    "trademark": "reports/m4_evidence/trademark_status.json",
    "performance": "reports/m4_evidence/performance_benchmark_report.json",
    "custody": "reports/m4_evidence/cold_storage_ceremony.json",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def validate_manifest() -> tuple[dict[str, Any], list[str]]:
    if not MANIFEST.exists():
        return {}, ["missing architecture/m4-mainnet-ready.json"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    issues: list[str] = []
    if manifest.get("milestone") != "M4":
        issues.append("manifest milestone must be M4")
    if "cannot be fabricated" not in manifest.get("claim_policy", ""):
        issues.append("manifest claim_policy must forbid fabricated evidence")
    hard_rules = "\n".join(str(item) for item in manifest.get("hard_rules", []))
    for token in ["No consensus", "explicit same-session signoff", "Legal"]:
        if token not in hard_rules:
            issues.append(f"manifest hard_rules missing token: {token}")
    ids = {item.get("id") for item in manifest.get("deliverables", []) if isinstance(item, dict)}
    missing = sorted(set(TOKEN_CHECKS) - ids)
    if missing:
        issues.append("missing M4 deliverables: " + ", ".join(missing))
    return manifest, issues


def source_gate() -> dict[str, Any]:
    manifest, issues = validate_manifest()
    results = []
    for gate_id, files in TOKEN_CHECKS.items():
        gate_issues = []
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
        "milestone": "M4",
        "mode": "source",
        "claim_level": "m4-source-complete-evidence-required" if not issues else "m4-source-incomplete",
        "deliverable_count": len(TOKEN_CHECKS),
        "pass_count": len([item for item in results if item["ok"]]),
        "blocker_count": len([item for item in results if not item["ok"]]),
        "results": results,
        "issues": issues,
        "cannot_claim_mainnet_ready_without_strict_evidence": True,
        "no_consensus_or_genesis_code_changed_by_this_gate": True,
        "manifest_schema": manifest.get("schema"),
    }


def strict_gate() -> dict[str, Any]:
    result = source_gate()
    evidence_issues: list[str] = []
    for _label, rel in STRICT_EVIDENCE.items():
        path = ROOT / rel
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
    result["strict_evidence"] = STRICT_EVIDENCE
    result["issues"] = list(result.get("issues", [])) + evidence_issues
    result["ok"] = not result["issues"]
    result["claim_level"] = "m4-mainnet-ready" if result["ok"] else "m4-strict-evidence-required"
    result["blocker_count"] = len(result["issues"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="reports/m4_readiness_source_report.json")
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
