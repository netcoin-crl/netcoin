from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def test_m5_manifest_is_evidence_gated() -> None:
    payload = json.loads((ROOT / "architecture/m5-mainnet-launch.json").read_text())
    assert payload["milestone"] == "M5"
    assert "cannot be fabricated" in payload["claim_policy"]
    assert any("No genesis block" in item for item in payload["hard_rules"])
    assert any("No seed deployment" in item for item in payload["hard_rules"])
    ids = {item["id"] for item in payload["deliverables"]}
    assert "t-zero-genesis-ceremony" in ids
    assert "t-plus-thirty-no-emergency-hardfork" in ids


def test_m5_source_gate_passes() -> None:
    proc = run(sys.executable, "tools/check_m5_readiness.py", "--out", "reports/m5_readiness_test_report.json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((ROOT / "reports/m5_readiness_test_report.json").read_text())
    assert payload["ok"] is True
    assert payload["claim_level"] == "m5-source-complete-evidence-required"
    assert payload["no_genesis_or_seed_deployment_by_this_gate"] is True


def test_m5_strict_gate_requires_real_launch_evidence() -> None:
    proc = run(
        sys.executable,
        "tools/check_m5_readiness.py",
        "--strict",
        "--out",
        "reports/m5_readiness_strict_test_report.json",
    )
    assert proc.returncode != 0
    payload = json.loads((ROOT / "reports/m5_readiness_strict_test_report.json").read_text())
    assert payload["ok"] is False
    assert payload["claim_level"] == "m5-strict-evidence-required"
    assert any("feature_freeze.json" in issue for issue in payload["issues"])
    assert any("genesis_ceremony.json" in issue for issue in payload["issues"])


def test_launch_plan_is_draft_only() -> None:
    proc = run(sys.executable, "tools/validate_m5_launch_plan.py", "--out", "reports/m5_launch_plan_test_report.json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((ROOT / "reports/m5_launch_plan_test_report.json").read_text())
    assert payload["ok"] is True
    assert payload["claim_level"] == "draft-only-not-approved-launch"
    assert payload["does_not_generate_or_mine_genesis"] is True
    assert payload["requires_m4_strict_completion"] is True


def test_m5_runner_source_profile_is_wired() -> None:
    proc = run(sys.executable, "tools/run_m5_release_candidate.py", "--profile", "source", "--dry-run", "--no-write")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert any("check_m5_readiness.py" in command for command in payload["commands"])
    assert any("validate_m5_launch_plan.py" in command for command in payload["commands"])


def test_m5_docs_include_no_overclaim_language() -> None:
    docs = [
        "docs/M5_MAINNET_LAUNCH_RUNBOOK.md",
        "docs/M5_GENESIS_CEREMONY.md",
        "docs/M5_LAUNCH_COMMUNICATIONS.md",
        "docs/M5_ROLLBACK_AND_HALT_POLICY.md",
    ]
    joined = "\n".join((ROOT / path).read_text() for path in docs)
    assert "Do **not** claim mainnet is live" in joined
    assert "does not mine genesis" in joined
    assert "Do **not** use" in joined
    assert "Do not silently rewrite history" in joined
