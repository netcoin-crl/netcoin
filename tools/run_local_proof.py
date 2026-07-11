#!/usr/bin/env python3
"""Run local Phase 1 proof gates and capture per-gate evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.local_proof_runner import local_proof_summary, run_local_proof  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin local proof gates with per-gate logs")
    parser.add_argument("--profile", choices=["sandbox", "strict"], default="sandbox")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="reports/local_proof_run_report.json")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--gate", action="append", default=[], help="run only the named gate id; repeatable")
    args = parser.parse_args()

    report = run_local_proof(
        profile=args.profile,
        timeout=args.timeout,
        out=args.out,
        write=not args.no_write,
        continue_on_fail=not args.stop_on_fail,
        gate_ids=args.gate or None,
    )
    print(json.dumps(local_proof_summary(report), indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
