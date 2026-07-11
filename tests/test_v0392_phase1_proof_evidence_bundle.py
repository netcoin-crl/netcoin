from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.proof_evidence import (
    REQUIRED_GATE_IDS,
    build_evidence_bundle,
    evidence_summary,
    load_proof_evidence_manifest,
    validate_proof_evidence_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_proof_evidence_manifest_is_valid() -> None:
    manifest = load_proof_evidence_manifest(ROOT / "architecture" / "proof-evidence-bundle.json")
    assert validate_proof_evidence_manifest(manifest, root=ROOT) == []
    assert str(manifest["version"]).startswith("0.39")
    gate_ids = {gate["gate_id"] for gate in manifest["gate_artifacts"]}
    assert REQUIRED_GATE_IDS.issubset(gate_ids)
    assert len(manifest["gate_artifacts"]) >= 8


def test_every_gate_has_paths_and_remediation() -> None:
    manifest = load_proof_evidence_manifest(ROOT / "architecture" / "proof-evidence-bundle.json")
    for gate in manifest["gate_artifacts"]:
        assert gate["paths"]
        assert gate["remediation"]
        assert isinstance(gate["required_for_strict"], bool)
        assert isinstance(gate["source_only_allowed"], bool)


def test_build_sandbox_evidence_bundle_summary() -> None:
    manifest = load_proof_evidence_manifest(ROOT / "architecture" / "proof-evidence-bundle.json")
    bundle = build_evidence_bundle(manifest, mode="sandbox", root=ROOT)
    summary = evidence_summary(bundle)
    assert str(summary["version"]).startswith("0.39")
    assert summary["gate_count"] >= 8
    assert summary["artifact_count"] >= 8
    assert bundle["claim_level"] == "source-checked-testnet"
    assert "remediation" in bundle


def test_checker_and_collector_run_without_writing() -> None:
    for command in [
        [sys.executable, "tools/check_proof_evidence.py"],
        [sys.executable, "tools/collect_proof_evidence.py", "--mode", "sandbox", "--no-write"],
    ]:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)
        assert result["ok"] is True


def test_v0392_gate_script_exists_and_identifies_release() -> None:
    script = (ROOT / "tools" / "run_v0392_check.py").read_text(encoding="utf-8")
    assert "0.39.2" in script
    assert "Phase 1 - Proof Evidence Bundle" in script
    assert "tests/test_v0392_phase1_proof_evidence_bundle.py" in script
