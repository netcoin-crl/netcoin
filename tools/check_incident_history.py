#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.incident_history import source_history_template, validate_incident_history
from netcoin.mainnet_readiness import load_evidence, stable_hash_json

REQUIRED = [
    "public_testnet_start",
    "incidents_or_no_incident_attestation",
    "runbook_links",
    "postmortem_links",
    "time_to_detect_minutes",
    "time_to_mitigate_minutes",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence", default="reports/mainnet_evidence/public_testnet_incidents.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.strict:
        payload, issues = load_evidence(ROOT / args.evidence)
        if payload:
            issues.extend(validate_incident_history(payload))
            if payload.get("ok") is not True:
                issues.append("evidence ok must be true")
            if payload.get("gate_id") not in (None, "public-testnet-incident-history"):
                issues.append("gate_id mismatch")
            for key in REQUIRED:
                if key not in payload and key != "incidents_or_no_incident_attestation":
                    issues.append(f"missing required evidence field: {key}")
            if "incidents_or_no_incident_attestation" not in payload and not (payload.get("incidents") or payload.get("no_incident_attestation")):
                issues.append("missing required evidence field: incidents_or_no_incident_attestation")
            body = {k: v for k, v in payload.items() if k != "evidence_hash"}
            if payload.get("evidence_hash") != stable_hash_json(body):
                issues.append("evidence_hash mismatch or missing")
        result = {
            "gate_id": "public-testnet-incident-history",
            "ok": not issues,
            "mode": "strict",
            "status": "strict-pass" if not issues else "strict-evidence-required",
            "issues": issues,
            "evidence_path": args.evidence,
        }
    else:
        result = source_history_template()
        result["gate_id"] = "public-testnet-incident-history"
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
