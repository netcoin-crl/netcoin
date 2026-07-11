#!/usr/bin/env python3
"""Build a proof triage report from local proof/evidence artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.proof_triage import (  # noqa: E402
    build_proof_triage_report,
    load_proof_triage_manifest,
    proof_triage_summary,
    render_triage_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NetCoin proof triage report")
    parser.add_argument("--out", default="reports/proof_triage_report.json")
    parser.add_argument("--summary-out", default="reports/proof_triage_summary.md")
    parser.add_argument("--local-report", default=None)
    parser.add_argument("--evidence-bundle", default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    manifest = load_proof_triage_manifest()
    report = build_proof_triage_report(
        manifest,
        root=ROOT,
        local_report_path=args.local_report,
        evidence_bundle_path=args.evidence_bundle,
    )
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary_out = ROOT / args.summary_out
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(render_triage_markdown(report), encoding="utf-8")
    print(json.dumps(proof_triage_summary(report), indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
