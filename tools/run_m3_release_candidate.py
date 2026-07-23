#!/usr/bin/env python3
"""Run the M3 decentralized-testnet release-candidate gate."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SOURCE_COMMANDS = [
    "python3 tools/check_m3_readiness.py --out reports/m3_readiness_source_report.json",
    "python3 -m pytest tests/test_m3_decentralized_testnet.py -q",
    "python3 tools/export_node_map.py --input api/nodes/map --out reports/m3_node_map_source_report.json",
    "python3 -m py_compile netcoin/addrv2.py netcoin/pex.py netcoin/bandwidth.py netcoin/p2p.py tools/check_m3_readiness.py tools/run_m3_release_candidate.py tools/export_node_map.py tools/validate_m3_soak_report.py",
]

STRICT_COMMANDS = [
    *SOURCE_COMMANDS,
    "python3 tools/check_m3_readiness.py --strict --out reports/m3_readiness_strict_report.json",
    "python3 tools/validate_m3_soak_report.py reports/m3_evidence/soak_30_day_report.json --out reports/m3_soak_validation_report.json",
]


def run(command: str, timeout: int) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(command, cwd=ROOT, shell=True, text=True, capture_output=True, timeout=timeout)
        return {
            "command": command,
            "returncode": proc.returncode,
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout_tail": proc.stdout[-1800:],
            "stderr_tail": proc.stderr[-1800:],
            "status": "pass" if proc.returncode == 0 else "fail",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout_tail": str(exc.stdout or "")[-1800:],
            "stderr_tail": str(exc.stderr or "")[-1800:],
            "status": "timeout",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["source", "strict"], default="source")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="reports/m3_release_candidate_report.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    args = parser.parse_args()
    commands = STRICT_COMMANDS if args.profile == "strict" else SOURCE_COMMANDS
    if args.dry_run:
        result = {"ok": True, "profile": args.profile, "dry_run": True, "commands": commands}
    else:
        runs = []
        for command in commands:
            entry = run(command, args.timeout)
            runs.append(entry)
            if args.stop_on_fail and entry["returncode"] != 0:
                break
        result = {
            "ok": all(item["returncode"] == 0 for item in runs),
            "profile": args.profile,
            "dry_run": False,
            "command_count": len(commands),
            "run_count": len(runs),
            "status_counts": {
                status: len([item for item in runs if item["status"] == status])
                for status in sorted({item["status"] for item in runs})
            },
            "runs": runs,
            "strict_evidence_required_for_operational_m3": args.profile == "strict",
        }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
