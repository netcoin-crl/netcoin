#!/usr/bin/env python3
"""Generate the Phase 1 release-readiness scorecard.

Sandbox mode runs deterministic checks available in restricted environments and
marks external-tool proofs as source_only where appropriate. Strict mode runs the
real proof commands from architecture/proof-hardening.json and fails if any are
missing, source-only, or blocked.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.proof_hardening import (  # noqa: E402
    ProofGateResult,
    load_proof_manifest,
    scorecard_from_results,
    validate_proof_manifest,
)

SANDBOX_COMMAND_OVERRIDES: dict[str, list[str]] = {
    "python-reference": [
        "python -m compileall -q netcoin tools",
        "python tools/run_parity_suite.py --no-write",
    ],
    "rust-workspace": ["python tools/check_rust_workspace.py"],
    "rust-parity": ["python tools/run_all_rust_parity.py --allow-missing-cargo --no-write"],
    "typescript-api": [
        "python tools/run_ts_api_contract_enforcement.py",
        "python tools/run_ts_openapi_codegen_parity.py --no-write",
    ],
    "browser-e2e": ["python tools/run_browser_e2e_matrix.py --out reports/browser_e2e_matrix_source_report.json"],
    "accessibility": [
        "python tools/run_accessibility_matrix.py --source-only --out reports/accessibility_source_report.json"
    ],
    "security-release": ["python tools/run_security_audit_prep.py"],
    "phase0-guardrails": [
        "python tools/check_product_architecture.py",
        "python tools/check_design_system.py",
        "python tools/check_product_simplification.py",
        "python tools/check_trust_interaction.py",
        "python tools/check_product_coherence.py",
        "python tools/check_phase0_complete.py",
    ],
}
SOURCE_ONLY_GATES = {"rust-parity", "browser-e2e", "accessibility"}


def _run_command(command: str, timeout: int) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, shell=True, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def _run_gate(gate: dict[str, Any], *, mode: str, timeout: int) -> ProofGateResult:
    gate_id = str(gate["id"])
    commands = (
        gate.get("strict_commands", [])
        if mode == "strict"
        else SANDBOX_COMMAND_OVERRIDES.get(gate_id, gate.get("sandbox_commands", []))
    )
    command_results: list[dict[str, Any]] = []
    issues: list[str] = []
    for command in commands:
        try:
            result = _run_command(str(command), timeout)
        except subprocess.TimeoutExpired:
            issues.append(f"timeout: {command}")
            command_results.append({"command": command, "returncode": -1, "timeout": True})
            continue
        command_results.append(result)
        if result["returncode"] != 0:
            issues.append(f"failed: {command}")
    if issues:
        status = "fail"
    elif mode != "strict" and gate_id in SOURCE_ONLY_GATES:
        status = "source_only"
    else:
        status = "pass"
    rich_issues = list(issues)
    if status == "source_only":
        rich_issues.append(
            "source-only proof; rerun Phase 1 readiness in --strict mode for professional release evidence"
        )
    return ProofGateResult(
        gate_id=gate_id,
        label=str(gate.get("label", gate_id)),
        status=status,
        mode=mode,
        command_count=len(commands),
        issues=tuple(rich_issues),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NetCoin release-readiness scorecard")
    parser.add_argument("--strict", action="store_true", help="run strict external-tool proof gates")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="reports/release_readiness_scorecard.json")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    manifest = load_proof_manifest()
    manifest_issues = validate_proof_manifest(manifest)
    if manifest_issues:
        scorecard = {
            "ok": False,
            "mode": "strict" if args.strict else "sandbox",
            "manifest_issues": manifest_issues,
        }
    else:
        mode = "strict" if args.strict else "sandbox"
        results = [_run_gate(gate, mode=mode, timeout=args.timeout) for gate in manifest.get("gate_groups", [])]
        scorecard = scorecard_from_results(manifest, results, mode=mode)
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": scorecard.get("ok"),
                "mode": scorecard.get("mode"),
                "claim_level": scorecard.get("claim_level"),
                "gate_count": scorecard.get("gate_count"),
                "status_counts": scorecard.get("status_counts"),
                "blocker_count": scorecard.get("blocker_count"),
                "caveat": scorecard.get("caveat"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if scorecard.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
