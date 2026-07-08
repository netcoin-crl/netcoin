#!/usr/bin/env python3
"""Create a deterministic full-suite test plan or run it by file with timeouts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_files() -> list[str]:
    return [str(p.relative_to(ROOT)) for p in sorted((ROOT / "tests").glob("test_*.py"))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="Run pytest per file with a timeout.")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--limit", type=int, default=0, help="Limit number of files for smoke validation.")
    ap.add_argument("--out", default="reports/full_suite_report.json", help="Write JSON report here.")
    args = ap.parse_args()
    files = test_files()
    if args.limit:
        files = files[: args.limit]
    report = {"generated_at": int(time.time()), "file_count": len(files), "files": files, "results": []}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    if not args.run:
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    ok = True
    for file in files:
        start = time.time()
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", file], cwd=ROOT, text=True, capture_output=True, timeout=args.timeout
        )
        rec = {
            "file": file,
            "returncode": proc.returncode,
            "seconds": round(time.time() - start, 2),
            "tail": (proc.stdout + proc.stderr).splitlines()[-12:],
        }
        report["results"].append(rec)
        if proc.returncode != 0:
            ok = False
    report["passed"] = ok
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
