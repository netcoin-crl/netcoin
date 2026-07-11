#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.mainnet_readiness import sha256_file, stable_hash_json, strict_evidence_gate

REQUIRED_EVIDENCE = [
    "auditor_name",
    "auditor_independence_statement",
    "scope_hash",
    "report_date",
    "critical_findings_zero_or_remediated",
    "report_artifact_hash",
]
SCOPE_PATHS = [
    "netcoin/consensus.py",
    "netcoin/tx.py",
    "netcoin/script.py",
    "netcoin/wallet.py",
    "netcoin/exchange_accounting.py",
    "netcoin/exchange_reserves.py",
    "core-rs/Cargo.toml",
    "api/src/server.ts",
    "docs/THREAT_MODEL.md",
    "docs/PRE_MAINNET_SECURITY_CHECKLIST.md",
]


def build_package() -> dict[str, object]:
    files = []
    for rel in SCOPE_PATHS:
        path = ROOT / rel
        files.append({"path": rel, "exists": path.exists(), "sha256": sha256_file(path) if path.exists() else ""})
    payload = {
        "gate_id": "external-crypto-security-audit",
        "ok": True,
        "mode": "audit-package-source",
        "status": "source-complete-evidence-required",
        "created_at": int(time.time()),
        "scope": files,
        "required_auditor_evidence": REQUIRED_EVIDENCE,
        "cannot_replace_external_audit": True,
    }
    payload["scope_hash"] = stable_hash_json({"scope": files})
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence", default="reports/mainnet_evidence/external_audit_evidence.json")
    parser.add_argument("--out", default="reports/external_audit_package.json")
    args = parser.parse_args()
    if args.strict:
        result = strict_evidence_gate(
            "external-crypto-security-audit", ROOT / args.evidence, REQUIRED_EVIDENCE
        ).to_dict()
        result["audit_package"] = build_package()
    else:
        result = build_package()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
