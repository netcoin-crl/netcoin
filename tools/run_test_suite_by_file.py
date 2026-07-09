#!/usr/bin/env python3
"""Run the NetCoin pytest suite one test file at a time.

The full NetCoin suite includes many chain-mining tests and app-layer smoke
flows. Running every file in one long pytest process can be memory-heavy in
small CI/sandbox environments, so this runner isolates each test module in its
own subprocess while still returning a single pass/fail result.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass
class Result:
    path: str
    status: str
    seconds: float
    output: str
    returncode: int


def discover(pattern: str, files: list[str] | None = None) -> list[pathlib.Path]:
    if files:
        paths = [pathlib.Path(item) for item in files]
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise SystemExit("missing test files: " + ", ".join(missing))
        return paths
    paths = sorted(pathlib.Path("tests").glob(pattern))
    if not paths:
        raise SystemExit(f"no tests matched tests/{pattern}")
    return paths


def run_one(
    path: pathlib.Path, timeout: int, pytest_args: list[str], disable_plugin_autoload: bool, capture: bool
) -> Result:
    env = dict(os.environ)
    env["PYTHONPATH"] = "." + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if disable_plugin_autoload:
        env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    cmd = [sys.executable, "-m", "pytest", "-q", *pytest_args, str(path)]
    start = time.monotonic()
    try:
        if capture:
            proc = subprocess.run(
                cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=timeout
            )
            output = proc.stdout or ""
        else:
            proc = subprocess.run(cmd, env=env, timeout=timeout)
            output = ""
        seconds = time.monotonic() - start
        returncode = proc.returncode
        status = "PASS" if returncode == 0 else f"FAIL({returncode})"
        # Pytest returns 5 when a file collects no runnable tests. For optional
        # backend differential suites that use importorskip at module import
        # time, the output is an intentional all-skipped result rather than a
        # failed test file.
        if returncode == 5 and "skipped" in output.lower():
            returncode = 0
            status = "SKIP"
        return Result(str(path), status, seconds, output, returncode)
    except subprocess.TimeoutExpired as exc:
        seconds = time.monotonic() - start
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return Result(str(path), "TIMEOUT", seconds, out, 124)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="test_*.py", help="glob under tests/, default: test_*.py")
    parser.add_argument("--files", nargs="+", help="explicit test files to run one at a time")
    parser.add_argument("--timeout", type=int, default=180, help="seconds allowed per test file")
    parser.add_argument("--stop-on-fail", action="store_true", help="stop at the first failing file")
    parser.add_argument(
        "--keep-pytest-plugins", action="store_true", help="do not set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"
    )
    parser.add_argument(
        "--capture", action="store_true", help="capture each pytest file's output instead of streaming it live"
    )
    parser.add_argument("pytest_args", nargs="*", help="extra pytest args, prefix with -- after runner options")
    args = parser.parse_args(argv)

    results: list[Result] = []
    for path in discover(args.pattern, args.files):
        print(f"[run] {path}", flush=True)
        result = run_one(path, args.timeout, args.pytest_args, not args.keep_pytest_plugins, args.capture)
        results.append(result)
        last_line = result.output.strip().splitlines()[-1] if result.output.strip() else ""
        suffix = f" {last_line}" if last_line else ""
        print(f"[{result.status}] {path} ({result.seconds:.1f}s){suffix}", flush=True)
        if result.returncode != 0:
            tail = "\n".join(result.output.strip().splitlines()[-80:])
            if tail:
                print(tail, flush=True)
            if args.stop_on_fail:
                break

    problems = [r for r in results if r.returncode != 0]
    print("\nSlowest test files:")
    for r in sorted(results, key=lambda item: item.seconds, reverse=True)[:12]:
        print(f"  {r.seconds:6.1f}s {r.status:10s} {r.path}")
    if problems:
        print("\nProblems:")
        for r in problems:
            print(f"  {r.status:10s} {r.path}")
        return 1
    print(f"\nAll {len(results)} test files passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
