from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.strict_proof_execution import (
    REQUIRED_CI_JOBS,
    load_strict_proof_manifest,
    strict_command_summary,
    validate_strict_proof_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_strict_proof_manifest_is_valid() -> None:
    manifest = load_strict_proof_manifest(ROOT / "architecture" / "strict-proof-execution.json")
    assert validate_strict_proof_manifest(manifest, root=ROOT) == []
    summary = strict_command_summary(manifest)
    assert summary["group_count"] >= 8
    assert summary["command_count"] >= 8
    assert summary["evidence_count"] >= 8


def test_strict_proof_manifest_requires_external_tool_proofs() -> None:
    manifest = load_strict_proof_manifest(ROOT / "architecture" / "strict-proof-execution.json")
    tools = {item["id"] for item in manifest["tool_requirements"]}
    assert {"python", "cargo", "node-npm", "playwright"}.issubset(tools)
    text = json.dumps(manifest)
    assert "cargo test --workspace" in text
    assert "npm ci && npm run ci:api" in text
    assert "--run-playwright" in text
    assert "--strict" in text


def test_proof_hardening_workflow_contains_required_jobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "proof-hardening.yml").read_text(encoding="utf-8")
    for job in REQUIRED_CI_JOBS:
        assert job in workflow
    for command in [
        "cargo test --workspace",
        "run_all_rust_parity.py --strict",
        "npm ci && npm run ci:api",
        "run_browser_e2e_matrix.py --run-playwright",
        "run_accessibility_matrix.py --strict",
        "run_release_readiness.py --strict",
    ]:
        assert command in workflow


def test_strict_proof_checker_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/check_strict_proof_execution.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["group_count"] >= 8


def test_print_strict_proof_plan_outputs_macos_commands() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/print_strict_proof_plan.py", "--profile", "macos", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["profile"] == "macos"
    assert "run_release_readiness.py --strict" in result["strict_command"]
