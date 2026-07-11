#!/usr/bin/env python3
"""Run the v0.39.4 proof triage release gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
COMMANDS: list[list[str]] = [
    [PY, "tools/check_proof_triage.py"],
    [
        PY,
        "tools/run_local_proof.py",
        "--profile",
        "sandbox",
        "--timeout",
        "120",
        "--no-write",
        "--gate",
        "rust-workspace",
        "--gate",
        "accessibility",
    ],
    [PY, "tools/run_proof_triage.py", "--no-write"],
    [PY, "-m", "pytest", "-q", "tests/test_v0394_phase1_proof_triage.py"],
]


def main() -> int:
    results: list[dict[str, Any]] = []
    for command in COMMANDS:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=240, check=False)
        results.append(
            {
                "command": " ".join(command),
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-1600:],
                "stderr_tail": proc.stderr[-1600:],
            }
        )
        if proc.returncode != 0:
            break
    failed = [item for item in results if not item["ok"]]
    report = {
        "ok": not failed,
        "version": "0.39.4",
        "phase": "Phase 1 - Proof Triage and CI Alignment",
        "command_count": len(results),
        "failed": failed,
        "claim_level": "proof triage validated; strict readiness still requires real external execution",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
