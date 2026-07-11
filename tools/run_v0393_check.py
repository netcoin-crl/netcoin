#!/usr/bin/env python3
"""Run the v0.39.3 local proof runner release gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
COMMANDS: list[list[str]] = [
    [PY, "tools/check_local_proof_runner.py"],
    [PY, "tools/run_local_proof.py", "--profile", "sandbox", "--timeout", "120", "--no-write", "--gate", "rust-workspace", "--gate", "accessibility"],
    [PY, "-m", "pytest", "-q", "tests/test_v0393_phase1_local_proof_runner.py"],
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
                "stdout_tail": proc.stdout[-1200:],
                "stderr_tail": proc.stderr[-1200:],
            }
        )
        if proc.returncode != 0:
            break
    failed = [item for item in results if not item["ok"]]
    report = {
        "ok": not failed,
        "version": "0.39.3",
        "phase": "Phase 1 - Local Proof Runner",
        "command_count": len(results),
        "failed": failed,
        "claim_level": "local proof runner validated; use --profile strict for strict local evidence",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
