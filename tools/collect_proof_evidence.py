#!/usr/bin/env python3
"""Collect NetCoin proof artifacts into one evidence bundle.

This command intentionally does not run expensive proof gates by default. Run the
appropriate proof commands first, then collect the reports into a hashed bundle.
Use --mode strict after running strict local/CI proof gates.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.proof_evidence import (  # noqa: E402
    build_evidence_bundle,
    evidence_summary,
    load_proof_evidence_manifest,
    validate_proof_evidence_manifest,
)


def run_refresh(timeout: int) -> None:
    commands = [
        [sys.executable, "tools/run_release_readiness.py", "--timeout", str(timeout)],
        [sys.executable, "tools/run_ts_api_contract_enforcement.py", "--out", "reports/ts_api_contract_report.json"],
        [
            sys.executable,
            "tools/run_accessibility_matrix.py",
            "--source-only",
            "--out",
            "reports/accessibility_source_report.json",
        ],
        [sys.executable, "tools/run_browser_e2e_matrix.py", "--out", "reports/browser_e2e_matrix_source_report.json"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=False, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect proof evidence into one hashed bundle")
    parser.add_argument("--mode", choices=["sandbox", "strict"], default="sandbox")
    parser.add_argument("--out", default="reports/proof_evidence_bundle.json")
    parser.add_argument("--refresh", action="store_true", help="refresh lightweight/source reports before collecting")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    manifest = load_proof_evidence_manifest()
    issues = validate_proof_evidence_manifest(manifest, root=ROOT)
    if issues:
        result = {"ok": False, "manifest_issues": issues}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    if args.refresh:
        run_refresh(args.timeout)
    bundle = build_evidence_bundle(manifest, mode=args.mode, root=ROOT)
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence_summary(bundle), indent=2, sort_keys=True))
    return 0 if bundle.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
