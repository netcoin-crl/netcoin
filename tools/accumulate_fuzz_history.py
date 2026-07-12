#!/usr/bin/env python3
"""Accumulate real NetCoin fuzz reports without inventing evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "reports" / "fuzz_history"
DEFAULT_OUT = ROOT / "reports" / "fuzz_history_summary.json"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_report(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("ok") is not True:
        return None
    if not isinstance(data.get("targets"), list) or "total_cases" not in data:
        return None
    return data


def _target_counts(report: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in report.get("targets", []):
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "unknown"))
        counts[target] = counts.get(target, 0) + int(item.get("cases", 0))
    return counts


def accumulate(history_dir: Path = DEFAULT_HISTORY_DIR, *, goal_cases: int = 100_000_000) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    target_totals: dict[str, int] = {}
    total_cases = 0
    for path in sorted(history_dir.glob("*.json")):
        report = _load_report(path)
        if report is None:
            continue
        cases = int(report.get("total_cases", 0))
        total_cases += cases
        for target, count in _target_counts(report).items():
            target_totals[target] = target_totals.get(target, 0) + count
        reports.append(
            {
                "file": display_path(path),
                "total_cases": cases,
                "seed": report.get("seed"),
                "iterations": report.get("iterations"),
                "duration_seconds": report.get("duration_seconds"),
            }
        )
    return {
        "ok": True,
        "schema": "netcoin-fuzz-history-v1",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "history_dir": display_path(history_dir),
        "report_count": len(reports),
        "total_cases": total_cases,
        "goal_cases": goal_cases,
        "goal_progress": round(total_cases / goal_cases, 8) if goal_cases else 0,
        "target_totals": dict(sorted(target_totals.items())),
        "reports": reports,
        "does_not_claim": [
            "100M fuzz target reached unless total_cases >= goal_cases",
            "external audit completion",
            "Rust executable differential coverage when cargo did not run",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Accumulate NetCoin fuzz-history JSON reports")
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--goal-cases", type=int, default=100_000_000)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = accumulate(args.history_dir, goal_cases=args.goal_cases)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
