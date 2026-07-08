#!/usr/bin/env python3
"""Coverage gate wrapper used by CI.

Runs pytest with JSON coverage output, enforces a repository-wide floor, and can
also enforce per-workstream floors so consensus/wallet/mempool/markets/storage/
API-auth coverage cannot be hidden by unrelated high-coverage files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

MODULE_GROUPS: dict[str, list[str]] = {
    "consensus": ["netcoin/consensus.py", "netcoin/chain.py", "netcoin/block.py"],
    "wallet": ["netcoin/wallet.py", "netcoin/signer.py", "netcoin/coin_control.py"],
    "mempool": ["netcoin/mempool.py", "netcoin/chain.py"],
    "markets": ["netcoin/apps/markets/"],
    "storage": ["netcoin/storage.py", "netcoin/storage_migrations.py"],
    "api_auth": ["netcoin/apps/auth.py"],
}


def _covered_percent_for_group(report: dict, prefixes: list[str]) -> float:
    covered = 0
    statements = 0
    files = report.get("files", {})
    for filename, data in files.items():
        normalized = filename.replace("\\", "/")
        if not any(normalized == prefix or normalized.startswith(prefix) for prefix in prefixes):
            continue
        summary = data.get("summary", {})
        covered += int(summary.get("covered_lines", 0))
        statements += int(summary.get("num_statements", 0))
    if statements == 0:
        return 100.0
    return covered * 100.0 / statements


def _parse_thresholds(value: str, default: int) -> dict[str, int]:
    thresholds: dict[str, int] = {}
    if not value:
        return thresholds
    for piece in value.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if ":" in piece:
            name, raw = piece.split(":", 1)
            thresholds[name.strip()] = int(raw.strip())
        else:
            thresholds[piece] = int(default)
    return thresholds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum", type=int, default=55, help="repository-wide coverage minimum")
    parser.add_argument(
        "--packages",
        default="consensus,wallet,mempool,markets,storage,api_auth",
        help="comma list of workstreams, optionally name:minimum",
    )
    parser.add_argument("--group-minimum", type=int, default=35, help="default per-workstream minimum")
    parser.add_argument("--json-out", default="coverage.json")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args()

    thresholds = _parse_thresholds(args.packages, args.group_minimum)
    print(
        "Coverage gate: repo_minimum={} group_minimum={} workstreams={}".format(
            args.minimum, args.group_minimum, thresholds or "none"
        )
    )
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--timeout=300",
        "--cov=netcoin",
        "--cov-report=term-missing",
        f"--cov-report=json:{args.json_out}",
        f"--cov-fail-under={int(args.minimum)}",
    ] + args.pytest_args
    test_rc = subprocess.call(cmd)
    if test_rc != 0:
        return test_rc

    report_path = Path(args.json_out)
    if not report_path.exists():
        print(f"coverage JSON report not found: {report_path}", file=sys.stderr)
        return 2
    report = json.loads(report_path.read_text())
    failures: list[str] = []
    for name, minimum in thresholds.items():
        prefixes = MODULE_GROUPS.get(name)
        if not prefixes:
            failures.append(f"unknown coverage group: {name}")
            continue
        pct = _covered_percent_for_group(report, prefixes)
        print(f"coverage[{name}]={pct:.2f}% minimum={minimum}%")
        if pct + 1e-9 < minimum:
            failures.append(f"{name}: {pct:.2f}% < {minimum}%")
    if failures:
        print("coverage gate failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
