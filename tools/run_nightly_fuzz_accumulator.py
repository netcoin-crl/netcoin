#!/usr/bin/env python3
"""Run nightly fuzz evidence and consensus parity comparison."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "reports" / "fuzz_history"
sys.path.insert(0, str(ROOT))

from tools.accumulate_fuzz_history import accumulate


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H%M%SZ")


def _run(cmd: list[str], *, timeout: int) -> dict[str, Any]:
    started = dt.datetime.now(dt.UTC)
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=os.environ.copy(),
    )
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "duration_seconds": round((dt.datetime.now(dt.UTC) - started).total_seconds(), 3),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_nightly(
    *,
    iterations: int,
    max_bytes: int,
    seed: int,
    history_dir: Path,
    summary_out: Path,
    timeout: int,
    allow_missing_cargo: bool,
) -> dict[str, Any]:
    stamp = _stamp()
    history_dir.mkdir(parents=True, exist_ok=True)
    fuzz_out = history_dir / f"{stamp}-fuzz.json"
    parity_out = history_dir / f"{stamp}-rust-consensus-parity.json"

    fuzz_cmd = [
        sys.executable,
        "-X",
        "dev",
        "-m",
        "netcoin",
        "fuzz",
        "--target",
        "all",
        "--iterations",
        str(iterations),
        "--max-bytes",
        str(max_bytes),
        "--seed",
        str(seed),
        "--out",
        str(fuzz_out),
    ]
    parity_cmd = [
        sys.executable,
        "tools/run_rust_consensus_parity.py",
        "--out",
        str(parity_out),
        "--timeout",
        str(timeout),
    ]
    if allow_missing_cargo:
        parity_cmd.append("--allow-missing-cargo")

    fuzz_run = _run(fuzz_cmd, timeout=timeout)
    parity_run = _run(parity_cmd, timeout=timeout)
    try:
        summary_report = accumulate(history_dir)
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(json.dumps(summary_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        accumulate_run = {"ok": True, "returncode": 0, "duration_seconds": 0, "command": ["accumulate()"]}
    except Exception as exc:
        summary_report = {}
        accumulate_run = {
            "ok": False,
            "returncode": 1,
            "duration_seconds": 0,
            "command": ["accumulate()"],
            "stderr_tail": f"{exc.__class__.__name__}: {exc}",
            "stdout_tail": "",
        }

    fuzz_report = _load_json(fuzz_out) if fuzz_out.exists() else {}
    parity_report = _load_json(parity_out) if parity_out.exists() else {}
    ok = bool(fuzz_run["ok"] and parity_run["ok"] and accumulate_run["ok"])
    return {
        "ok": ok,
        "schema": "netcoin-nightly-fuzz-v1",
        "stamp": stamp,
        "fuzz_report": display_path(fuzz_out),
        "rust_consensus_parity_report": display_path(parity_out),
        "history_summary": display_path(summary_out),
        "fuzz_total_cases": fuzz_report.get("total_cases", 0),
        "history_total_cases": summary_report.get("total_cases", 0),
        "rust_consensus_parity_ok": parity_report.get("ok"),
        "rust_consensus_parity_mode": parity_report.get("mode"),
        "runs": {
            "fuzz": fuzz_run,
            "rust_consensus_parity": parity_run,
            "accumulate": accumulate_run,
        },
        "does_not_claim": [
            "100M fuzz target reached",
            "external audit completion",
            "Rust executable differential coverage when mode is source-only",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin nightly fuzz accumulator")
    parser.add_argument("--iterations", type=int, default=2_000_000)
    parser.add_argument("--max-bytes", type=int, default=256)
    parser.add_argument("--seed", type=int, default=1234567)
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "nightly_fuzz_report.json")
    parser.add_argument("--allow-missing-cargo", action="store_true")
    args = parser.parse_args()

    report = run_nightly(
        iterations=args.iterations,
        max_bytes=args.max_bytes,
        seed=args.seed,
        history_dir=args.history_dir,
        summary_out=args.summary_out or (args.out.parent / "fuzz_history_summary.json"),
        timeout=args.timeout,
        allow_missing_cargo=args.allow_missing_cargo,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
