from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.proof_hardening import (
    ProofGateResult,
    load_proof_manifest,
    scorecard_from_results,
    validate_proof_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase1_manifest_is_valid() -> None:
    manifest = load_proof_manifest(ROOT / "architecture" / "proof-hardening.json")
    assert validate_proof_manifest(manifest) == []
    assert manifest["inherits_from"] == "architecture/phase0-completion.json"
    assert len(manifest["gate_groups"]) >= 8


def test_required_phase1_gates_are_present() -> None:
    manifest = load_proof_manifest(ROOT / "architecture" / "proof-hardening.json")
    gate_ids = {gate["id"] for gate in manifest["gate_groups"]}
    assert {
        "python-reference",
        "rust-workspace",
        "rust-parity",
        "typescript-api",
        "browser-e2e",
        "accessibility",
        "security-release",
        "phase0-guardrails",
    }.issubset(gate_ids)


def test_release_scorecard_marks_source_only_as_non_professional() -> None:
    manifest = load_proof_manifest(ROOT / "architecture" / "proof-hardening.json")
    results = [
        ProofGateResult("python-reference", "Python", "pass", "sandbox", 2),
        ProofGateResult("rust-parity", "Rust Parity", "source_only", "sandbox", 1),
    ]
    scorecard = scorecard_from_results(manifest, results, mode="sandbox")
    assert scorecard["ok"] is True
    assert scorecard["claim_level"] == "source-checked-testnet"
    assert scorecard["blocker_count"] == 1
    assert "not enough" in scorecard["caveat"]


def test_all_rust_parity_runner_exists_and_lists_all_lanes() -> None:
    text = (ROOT / "tools" / "run_all_rust_parity.py").read_text(encoding="utf-8")
    for lane in ["consensus", "mempool", "wallet", "markets", "signer", "p2p", "indexer"]:
        assert f'"{lane}"' in text
    assert "--allow-missing-cargo" in text
    assert "--strict" in text


def test_accessibility_matrix_source_check_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/run_accessibility_matrix.py", "--source-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["mode"] == "source-only"


def test_proof_hardening_checker_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/check_proof_hardening.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["gate_count"] >= 8
