#!/usr/bin/env python3
"""Run executable NetCoin parity vectors and write a report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.parity_suite import run_parity_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin parity vectors")
    parser.add_argument("--out", default="reports/parity_suite_report.json")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = run_parity_suite(ROOT)
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "total", "passed", "failed", "vector_fingerprint")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
