#!/usr/bin/env python3
"""Source and evidence gate for M2 trust hardening."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "m2-trust-hardening.json"

TOKEN_CHECKS = {
    "hardware-wallet-contract": {
        "netcoin/hardware_wallet.py": ["HardwareSignRequest", "ledger", "trezor", "webhid", "webusb"],
        "docs/HARDWARE_WALLET_INTEGRATION.md": ["Ledger", "Trezor", "physical-device"],
    },
    "psbt-round-trip": {"netcoin/psbt.py": ["PartiallySignedTransaction", "combine", "finalize", "extract"]},
    "fee-bumping": {"netcoin/fee_bump.py": ["create_rbf_replacement", "create_cpfp_child", "FeeBumpPlan"]},
    "watch-only-xpub-descriptors": {
        "netcoin/descriptors.py": ["descriptor_to_address", "multisig_descriptor"],
        "tests/test_hd.py": ["xpub", "watch_only"],
    },
    "reproducible-builds": {
        "Dockerfile.repro": ["SOURCE_DATE_EPOCH", "generate_sbom", "generate_slsa_provenance"],
        "tools/verify_reproducible_build.py": [
            "normalized source archive",
            "independent_builder_required_for_strict_m2",
        ],
    },
    "signed-releases-sbom-provenance": {
        "tools/sign_release.py": ["signature"],
        "tools/verify_release.py": ["verify"],
        "tools/generate_sbom.py": ["netcoin-source-sbom-v1"],
        "tools/generate_slsa_provenance.py": ["slsa.dev/provenance"],
        "sites/keys/index.html": ["NetCoin release keys", "minisign", "cosign"],
    },
    "fuzz-corpus": {"docs/FUZZ_CORPUS_PLAN.md": ["100M", "consensus", "mempool", "tx parse"]},
    "bug-bounty-and-audit": {
        "docs/BUG_BOUNTY_SCOPE.md": ["$5,000", "Critical", "private-key"],
        "docs/AUDIT_SCOPING_PACKAGE.md": ["Trail of Bits", "OpenZeppelin", "NCC Group"],
        "sites/security/bug-bounty.html": ["Bug bounty", "draft", "scope"],
    },
    "threat-model-cve-review": {
        "docs/THREAT_MODEL.md": ["Threat", "wallet"],
        "docs/BITCOIN_CVE_THREAT_REVIEW.md": ["inflation", "Merkle", "RBF", "PSBT"],
    },
}

SOURCE_COMMANDS = [
    "python3 -m py_compile netcoin/hardware_wallet.py netcoin/fee_bump.py tools/check_m2_readiness.py tools/run_m2_release_candidate.py tools/verify_reproducible_build.py tools/generate_slsa_provenance.py",
    "python3 -m pytest tests/test_m2_trust_hardening.py tests/test_m2_fee_bump.py -q",
    "python3 tools/verify_reproducible_build.py --out reports/reproducible_build_source_report.json",
    "python3 tools/generate_sbom.py --out dist/netcoin-sbom.json",
    "python3 tools/generate_slsa_provenance.py --subject dist/netcoin-sbom.json --out dist/netcoin-slsa-provenance.json",
]

STRICT_EVIDENCE = {
    "hardware_wallet_device": "reports/m2_evidence/hardware_wallet_device_evidence.json",
    "independent_repro_build": "reports/m2_evidence/independent_repro_build.json",
    "release_signing_key_ceremony": "reports/m2_evidence/release_signing_key_ceremony.json",
    "fuzz_100m_report": "reports/m2_evidence/fuzz_100m_report.json",
    "audit_scoping_notes": "reports/m2_evidence/audit_scoping_notes.json",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate_manifest() -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if not MANIFEST.exists():
        return {}, ["missing architecture/m2-trust-hardening.json"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("milestone") != "M2":
        issues.append("manifest milestone must be M2")
    if "evidence" not in str(manifest.get("claim_policy", "")).lower():
        issues.append("manifest claim_policy must require evidence for operational completion")
    deliverables = manifest.get("deliverables", [])
    ids = {item.get("id") for item in deliverables if isinstance(item, dict)}
    missing = sorted(set(TOKEN_CHECKS) - ids)
    if missing:
        issues.append("missing M2 deliverables: " + ", ".join(missing))
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
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in tokens:
                if token not in text:
                    gate_issues.append(f"{rel} missing token: {token}")
        results.append({"id": gate_id, "ok": not gate_issues, "issues": gate_issues})
        issues.extend(f"{gate_id}: {issue}" for issue in gate_issues)
    return {
        "ok": not issues,
        "milestone": "M2",
        "mode": "source",
        "claim_level": "m2-source-complete-evidence-required" if not issues else "m2-source-incomplete",
        "deliverable_count": len(TOKEN_CHECKS),
        "pass_count": len([r for r in results if r["ok"]]),
        "blocker_count": len([r for r in results if not r["ok"]]),
        "results": results,
        "issues": issues,
        "cannot_claim_operational_m2_without_strict_evidence": True,
        "manifest_version": manifest.get("schema"),
    }


def strict_gate() -> dict[str, Any]:
    result = source_gate()
    evidence_issues = []
    for label, rel in STRICT_EVIDENCE.items():
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
    result["claim_level"] = "m2-operationally-verified" if result["ok"] else "m2-strict-evidence-required"
    result["blocker_count"] = len(result["issues"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="reports/m2_readiness_source_report.json")
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
