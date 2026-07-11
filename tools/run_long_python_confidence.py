#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.mainnet_readiness import strict_evidence_gate

REQUIRED_EVIDENCE = ["all_test_files_passed", "zero_timeouts", "slowest_files_recorded", "parity_fingerprint_recorded"]


def run_cmd(cmd: list[str], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "seconds": round(time.monotonic() - started, 2),
            "stdout_tail": proc.stdout[-3000:],
            "stderr_tail": proc.stderr[-3000:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
        return {
            "command": cmd,
            "returncode": 124,
            "seconds": round(time.monotonic() - started, 2),
            "stdout_tail": out[-3000:],
            "stderr_tail": err[-3000:],
            "timeout": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--timeout", type=int, default=240, help="seconds per command")
    parser.add_argument("--suite-timeout", type=int, default=180, help="seconds per test file inside runner")
    parser.add_argument("--evidence", default="reports/mainnet_evidence/long_python_suite_evidence.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.strict:
        # Prefer executing the full by-file suite. If the caller supplies a strict evidence file instead,
        # they can use tools/run_mainnet_readiness.py to validate that transcript separately.
        parity = run_cmd([sys.executable, "tools/run_parity_suite.py", "--no-write"], args.timeout)
        suite = run_cmd([sys.executable, "tools/run_test_suite_by_file.py", "--timeout", str(args.suite_timeout)], args.timeout)
        issues = []
        if parity["returncode"] != 0:
            issues.append("parity suite failed")
        if suite["returncode"] != 0:
            issues.append("long Python by-file suite failed or timed out")
        result = {
            "gate_id": "long-python-suite-confidence",
            "ok": not issues,
            "mode": "strict-execution",
            "issues": issues,
            "parity": parity,
            "suite": suite,
            "all_test_files_passed": suite["returncode"] == 0,
            "zero_timeouts": not suite.get("timeout"),
        }
    elif args.evidence and Path(ROOT / args.evidence).exists():
        result = strict_evidence_gate("long-python-suite-confidence", ROOT / args.evidence, REQUIRED_EVIDENCE).to_dict()
    else:
        test_files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*.py"))
        result = {
            "gate_id": "long-python-suite-confidence",
            "ok": True,
            "mode": "source",
            "status": "source-complete-evidence-required",
            "test_file_count": len(test_files),
            "runner": "tools/run_test_suite_by_file.py --timeout 180",
            "required_evidence": REQUIRED_EVIDENCE,
        }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
