from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.local_proof_runner import (
    REQUIRED_GATE_IDS,
    load_local_proof_manifest,
    local_proof_summary,
    run_local_proof,
    validate_local_proof_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_local_proof_manifest_is_valid() -> None:
    manifest = load_local_proof_manifest(ROOT / "architecture" / "local-proof-runner.json")
    assert validate_local_proof_manifest(manifest, root=ROOT) == []
    assert manifest["version"] == "0.39.3"
    assert manifest["phase"] == "Phase 1 - Local Proof Runner"
    assert set(manifest["required_gate_ids"]) >= REQUIRED_GATE_IDS
    assert "rust-parity" in manifest["source_only_gates"]


def test_local_proof_runner_sandbox_no_write_summary() -> None:
    report = run_local_proof(profile="sandbox", timeout=120, write=False, gate_ids=["rust-workspace", "accessibility"])
    summary = local_proof_summary(report)
    assert summary["version"] == "0.39.3"
    assert summary["profile"] == "sandbox"
    assert summary["gate_count"] == 2
    assert summary["status_counts"]["fail"] == 0
    assert summary["status_counts"]["source_only"] >= 1
    assert report["claim_level"] == "source-checked-testnet"


def test_local_proof_checker_and_runner_cli() -> None:
    commands = [
        [sys.executable, "tools/check_local_proof_runner.py"],
        [
            sys.executable,
            "tools/run_local_proof.py",
            "--profile",
            "sandbox",
            "--timeout",
            "120",
            "--no-write",
            "--gate",
            "rust-workspace",
            "--gate",
            "accessibility",
        ],
    ]
    for command in commands:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=180)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        parsed = json.loads(proc.stdout)
        assert parsed["ok"] is True


def test_local_proof_runner_writes_artifacts(tmp_path: Path) -> None:
    out = "reports/test_local_proof_run_report.json"
    report = run_local_proof(profile="sandbox", timeout=120, out=out, write=True, gate_ids=["rust-workspace"])
    assert report["ok"] is True
    out_path = ROOT / out
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["run_directory"]
    run_dir = ROOT / data["run_directory"]
    assert run_dir.exists()
    first_gate = data["gates"][0]
    assert Path(ROOT / first_gate["artifacts"]["json"]).exists()
    assert Path(ROOT / first_gate["artifacts"]["log"]).exists()


def test_v0393_gate_script_exists_and_identifies_release() -> None:
    script = (ROOT / "tools" / "run_v0393_check.py").read_text(encoding="utf-8")
    assert "0.39.3" in script
    assert "Phase 1 - Local Proof Runner" in script
    assert "tests/test_v0393_phase1_local_proof_runner.py" in script
