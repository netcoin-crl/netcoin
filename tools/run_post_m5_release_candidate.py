#!/usr/bin/env python3
"""Run source or strict checks for the post-M5 engineering backlog."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_COMMANDS = [
    [sys.executable, "tools/check_post_m5_engineering.py", "--out", "reports/post_m5_engineering_source_report.json"],
    [
        sys.executable,
        "-m",
        "py_compile",
        "netcoin/offline_signing.py",
        "netcoin/hardware_bridge.py",
        "netcoin/p2p_public_hardening.py",
        "netcoin/versionbits.py",
        "netcoin/genesis_manifest.py",
        "netcoin/liquidity.py",
        "netcoin/ecosystem.py",
        "tools/check_post_m5_engineering.py",
    ],
    [sys.executable, "-m", "compileall", "-q", "netcoin", "tools", "tests"],
]


def run(command: list[str], timeout: int) -> dict:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "status": "pass" if proc.returncode == 0 else "fail",
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["source", "strict"], default="source")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    commands = list(SOURCE_COMMANDS)
    if args.profile == "strict":
        commands.append(
            [
                sys.executable,
                "tools/check_post_m5_engineering.py",
                "--strict",
                "--out",
                "reports/post_m5_engineering_strict_report.json",
            ]
        )
    runs = []
    for command in commands:
        runs.append(run(command, args.timeout))
        if runs[-1]["returncode"] != 0:
            break
    result = {
        "schema": "netcoin-post-m5-release-candidate-run-v1",
        "profile": args.profile,
        "ok": all(item["returncode"] == 0 for item in runs),
        "runs": runs,
        "run_count": len(runs),
        "does_not_deploy_mine_or_activate": True,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
