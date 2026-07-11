#!/usr/bin/env python3
"""Run all Rust executable parity lanes and produce one combined report.

Default mode is strict enough for local machines with Cargo. Use
--allow-missing-cargo in restricted sandboxes; that mode remains source-only and
must not be used as a professional readiness claim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANES = [
    ("consensus", "tools/run_rust_consensus_parity.py"),
    ("mempool", "tools/run_rust_mempool_parity.py"),
    ("wallet", "tools/run_rust_wallet_parity.py"),
    ("markets", "tools/run_rust_markets_parity.py"),
    ("signer", "tools/run_rust_signer_parity.py"),
    ("p2p", "tools/run_rust_p2p_parity.py"),
    ("indexer", "tools/run_rust_indexer_parity.py"),
]


def _run_lane(lane: str, script: str, *, allow_missing_cargo: bool, timeout: int) -> dict[str, Any]:
    cmd = [sys.executable, script, "--no-write"]
    if allow_missing_cargo:
        cmd.append("--allow-missing-cargo")
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    parsed: dict[str, Any] | None = None
    if proc.stdout.strip():
        try:
            decoder = json.JSONDecoder()
            stripped = proc.stdout.lstrip()
            parsed, _ = decoder.raw_decode(stripped)
        except json.JSONDecodeError:
            # Some lane scripts may print non-JSON diagnostics. Keep raw output.
            parsed = None
    status = "pass" if proc.returncode == 0 else "fail"
    mode = "unknown"
    cargo_available = None
    if parsed:
        mode = str(parsed.get("mode", mode))
        cargo_available = parsed.get("cargo_available")
        if mode.startswith("source-only"):
            status = "source_only" if proc.returncode == 0 else "fail"
    return {
        "lane": lane,
        "script": script,
        "status": status,
        "returncode": proc.returncode,
        "mode": mode,
        "cargo_available": cargo_available,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all NetCoin Rust parity lanes")
    parser.add_argument("--allow-missing-cargo", action="store_true", help="allow source-only parity checks when Cargo is missing")
    parser.add_argument("--strict", action="store_true", help="fail if any lane is source-only")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="reports/all_rust_parity_report.json")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    results = []
    for lane, script in LANES:
        results.append(_run_lane(lane, script, allow_missing_cargo=args.allow_missing_cargo, timeout=args.timeout))
    source_only = [item["lane"] for item in results if item.get("status") == "source_only"]
    failed = [item["lane"] for item in results if item.get("status") == "fail"]
    ok = not failed and not (args.strict and source_only)
    report = {
        "ok": ok,
        "mode": "strict" if args.strict else ("allow-missing-cargo" if args.allow_missing_cargo else "cargo"),
        "lane_count": len(results),
        "failed_lanes": failed,
        "source_only_lanes": source_only,
        "results": results,
        "caveat": "source-only lanes are not professional readiness proof" if source_only else None,
    }
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["ok", "mode", "lane_count", "failed_lanes", "source_only_lanes"]}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
