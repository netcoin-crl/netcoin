#!/usr/bin/env python3
"""Run the v0.39.1 strict-proof execution bridge gate.

This gate validates the strict-proof playbook itself. The heavier proof commands
remain available through tools/run_release_readiness.py and the CI workflow.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
COMMANDS: list[list[str]] = [
    [PY, "tools/check_strict_proof_execution.py"],
    [PY, "-m", "pytest", "-q", "tests/test_v0391_phase1_strict_proof_execution.py"],
]


def main() -> int:
    results: list[dict[str, Any]] = []
    for command in COMMANDS:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120, check=False)
        results.append(
            {
                "command": " ".join(command),
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-800:],
                "stderr_tail": proc.stderr[-800:],
            }
        )
        if proc.returncode != 0:
            break
    failed = [item for item in results if not item["ok"]]
    report = {
        "ok": not failed,
        "version": "0.39.1",
        "phase": "Phase 1 - Strict Proof Execution Bridge",
        "command_count": len(results),
        "failed": failed,
        "claim_level": "strict-proof-playbook validated; run tools/run_release_readiness.py --strict for full external proof",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
