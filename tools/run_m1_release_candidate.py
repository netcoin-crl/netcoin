#!/usr/bin/env python3
"""Run or print the M1 release-candidate verification plan.

This runner is intentionally local-only. It never deploys to seeds, never reads
secrets, and never claims live production health. Its job is to make the M1
source package reviewable before an operator decides whether to push.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Gate:
    gate_id: str
    label: str
    command: str
    profile: str = "source"
    requires: tuple[str, ...] = ()


SOURCE_GATES: tuple[Gate, ...] = (
    Gate(
        "m1-readiness-source",
        "M1 source readiness markers",
        "python3 tools/check_m1_readiness.py --out reports/m1_readiness_source_report.json",
    ),
    Gate(
        "site-ui-polish",
        "Static site UI polish guard",
        "python3 tools/check_site_ui_polish.py",
    ),
    Gate(
        "m1-source-tests",
        "M1 source regression tests",
        "python3 -m pytest tests/test_m1_readiness_gate.py tests/test_m1_ci_gate_wiring.py tests/test_m1_wallet_e2e_source.py tests/test_m1_wallet_regressions.py tests/test_m1_status_page.py tests/test_m1_faucet_hardening.py tests/test_m1_explorer_mempool_live.py tests/test_m1_incident_response_runbook.py tests/test_m1_testnet_user_journey.py tests/test_m1_testnet_feedback_intake.py tests/test_m1_testnet_pilot_plan.py tests/test_m1_live_smoke_tool.py -q",
    ),
    Gate(
        "wallet-js-syntax",
        "Wallet JavaScript syntax",
        "node --check sites/wallet/wallet-app.js && node --check webwallet-browser/public/wallet-app.js",
        requires=("node",),
    ),
    Gate(
        "explorer-status-js-syntax",
        "Explorer and status JavaScript syntax",
        "node --check sites/explorer/explorer-pro.js && node --check sites/status/status.js && node --check sites/tests/e2e/m1-wallet-workflow.spec.js",
        requires=("node",),
    ),
    Gate(
        "m1-live-smoke-plan",
        "M1 live smoke dry-run plan",
        "python3 tools/check_m1_live_smoke.py --out reports/m1_live_smoke_plan.json",
    ),
)

STRICT_GATES: tuple[Gate, ...] = (
    Gate(
        "black",
        "Black formatting",
        ".venv/bin/python -m black --check netcoin tests tools",
        profile="strict",
    ),
    Gate(
        "python-suite",
        "Full Python suite",
        ".venv/bin/python -m pytest tests/ -q",
        profile="strict",
    ),
    Gate(
        "coverage-gate",
        "Coverage gate",
        ".venv/bin/python tools/coverage_gate.py --minimum 55 --group-minimum 35 --packages consensus:40,wallet:35,mempool:35,markets:35,storage:35,api_auth:50",
        profile="strict",
    ),
    Gate(
        "parity",
        "Python/Rust/TS parity suite",
        ".venv/bin/python tools/run_parity_suite.py",
        profile="strict",
    ),
    Gate(
        "rust-workspace",
        "Rust workspace",
        "cargo test --workspace --manifest-path core-rs/Cargo.toml",
        profile="strict",
        requires=("cargo",),
    ),
    Gate(
        "typescript-parity",
        "TypeScript parity",
        "cd api && npm run parity",
        profile="strict",
        requires=("npm",),
    ),
    Gate(
        "typescript-ci",
        "TypeScript API CI",
        "cd api && npm run ci:api",
        profile="strict",
        requires=("npm",),
    ),
    Gate(
        "browser-e2e",
        "Browser E2E matrix",
        "python3 tools/run_browser_e2e_matrix.py --run-playwright",
        profile="strict",
    ),
    Gate(
        "accessibility-strict",
        "Accessibility strict matrix",
        "python3 tools/run_accessibility_matrix.py --strict",
        profile="strict",
    ),
    Gate(
        "local-proof",
        "Strict local proof runner",
        "python3 tools/run_local_proof.py --profile strict --timeout 300",
        profile="strict",
    ),
)


DOES_NOT_CLAIM = (
    "live seed deployment",
    "real CAPTCHA credentials",
    "external audit completion",
    "hardware wallet support",
    "independent-node decentralization",
)


def selected_gates(profile: str) -> list[Gate]:
    gates = list(SOURCE_GATES)
    if profile == "strict":
        gates.extend(STRICT_GATES)
    return gates


def missing_requirements(gate: Gate) -> list[str]:
    missing: list[str] = []
    for requirement in gate.requires:
        if shutil.which(requirement) is None:
            missing.append(requirement)
    return missing


def run_command(command: str, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def execute_gates(gates: list[Gate], *, dry_run: bool, timeout: int, stop_on_fail: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for gate in gates:
        missing = missing_requirements(gate)
        result: dict[str, Any] = {
            "id": gate.gate_id,
            "label": gate.label,
            "profile": gate.profile,
            "command": gate.command,
            "status": "pending",
            "missing_requirements": missing,
        }
        if dry_run:
            result["status"] = "planned"
            results.append(result)
            continue
        if missing:
            result["status"] = "blocked"
            result["issues"] = [f"missing executable: {name}" for name in missing]
            results.append(result)
            if stop_on_fail:
                break
            continue
        try:
            command_result = run_command(gate.command, timeout)
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["issues"] = [f"timed out after {timeout}s"]
            results.append(result)
            if stop_on_fail:
                break
            continue
        result.update(command_result)
        result["status"] = "pass" if command_result["returncode"] == 0 else "fail"
        if result["status"] != "pass" and stop_on_fail:
            results.append(result)
            break
        results.append(result)
    return results


def build_report(profile: str, results: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    incomplete_statuses = {"fail", "blocked", "timeout"}
    incomplete = [str(result["id"]) for result in results if result["status"] in incomplete_statuses]
    ok = not incomplete and len(results) == len(selected_gates(profile))
    if dry_run:
        ok = True
    return {
        "ok": ok,
        "scope": "M1 release-candidate verification",
        "profile": profile,
        "dry_run": dry_run,
        "gate_count": len(results),
        "status_counts": counts,
        "incomplete": incomplete,
        "does_not_claim": list(DOES_NOT_CLAIM),
        "gates": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the NetCoin M1 release-candidate verification plan.")
    parser.add_argument("--profile", choices=["source", "strict"], default="source")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="reports/m1_release_candidate_report.json")
    parser.add_argument("--dry-run", action="store_true", help="write the plan without running commands")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    args = parser.parse_args()

    results = execute_gates(
        selected_gates(args.profile),
        dry_run=args.dry_run,
        timeout=args.timeout,
        stop_on_fail=args.stop_on_fail,
    )
    report = build_report(args.profile, results, args.dry_run)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
