#!/usr/bin/env python3
"""Run NetCoin browser E2E tests with local static serving.

This runner keeps the workflow deterministic for CI/local use. If Playwright is
not installed it emits a clear skipped report instead of hiding the missing
browser toolchain behind a shell failure.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--report", default="reports/browser_e2e_report.json")
    args = ap.parse_args()
    REPORTS.mkdir(exist_ok=True)
    npx = shutil.which("npx")
    report = {"generated_at": int(time.time()), "port": args.port, "status": "not-run", "steps": []}
    if not npx:
        report.update({"status": "skipped", "reason": "npx/playwright not installed"})
        (ROOT / args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    env = os.environ.copy()
    env.setdefault("PLAYWRIGHT_BASE_URL", f"http://127.0.0.1:{args.port}")
    env["PLAYWRIGHT_SKIP_WEBSERVER"] = "1"
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(args.port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(1.0)
        cmd = [npx, "playwright", "test", "sites/tests/e2e", "webwallet-browser/tests/e2e", "--reporter=list"]
        start = time.time()
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=args.timeout)
        report.update(
            {
                "status": "passed" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "seconds": round(time.time() - start, 2),
                "tail": (proc.stdout + proc.stderr).splitlines()[-40:],
            }
        )
        return_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        report.update({"status": "timeout", "seconds": args.timeout, "tail": str(exc).splitlines()[-20:]})
        return_code = 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    (ROOT / args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
