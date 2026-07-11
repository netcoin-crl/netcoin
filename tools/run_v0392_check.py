#!/usr/bin/env python3
"""Run the v0.39.2 proof-evidence bundle release gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
COMMANDS: list[list[str]] = [
    [PY, "tools/check_proof_evidence.py"],
    [PY, "tools/collect_proof_evidence.py", "--mode", "sandbox", "--no-write"],
    [PY, "-m", "pytest", "-q", "tests/test_v0392_phase1_proof_evidence_bundle.py"],
]


def main() -> int:
    results: list[dict[str, Any]] = []
    for command in COMMANDS:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180, check=False)
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
        "version": "0.39.2",
        "phase": "Phase 1 - Proof Evidence Bundle",
        "command_count": len(results),
        "failed": failed,
        "claim_level": "proof-evidence bundling validated; run collect_proof_evidence.py --mode strict after strict proof gates",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
