from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def test_m4_manifest_is_evidence_gated() -> None:
    payload = json.loads((ROOT / "architecture/m4-mainnet-ready.json").read_text())
    assert payload["milestone"] == "M4"
    assert "cannot be fabricated" in payload["claim_policy"]
    assert any("No consensus" in item for item in payload["hard_rules"])
    ids = {item["id"] for item in payload["deliverables"]}
    assert "version-bits-checkpoint-signoff" in ids
    assert "legal-risk-posture" in ids


def test_m4_source_gate_passes() -> None:
    proc = run(sys.executable, "tools/check_m4_readiness.py", "--out", "reports/m4_readiness_test_report.json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((ROOT / "reports/m4_readiness_test_report.json").read_text())
    assert payload["ok"] is True
    assert payload["claim_level"] == "m4-source-complete-evidence-required"
    assert payload["no_consensus_or_genesis_code_changed_by_this_gate"] is True


def test_m4_strict_gate_requires_real_evidence() -> None:
    proc = run(
        sys.executable,
        "tools/check_m4_readiness.py",
        "--strict",
        "--out",
        "reports/m4_readiness_strict_test_report.json",
    )
    assert proc.returncode != 0
    payload = json.loads((ROOT / "reports/m4_readiness_strict_test_report.json").read_text())
    assert payload["ok"] is False
    assert payload["claim_level"] == "m4-strict-evidence-required"
    assert any("external_audit_completion.json" in issue for issue in payload["issues"])


def test_distribution_manifest_is_draft_only() -> None:
    proc = run(
        sys.executable, "tools/validate_mainnet_distribution.py", "--out", "reports/m4_distribution_test_report.json"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((ROOT / "reports/m4_distribution_test_report.json").read_text())
    assert payload["ok"] is True
    assert payload["claim_level"] == "draft-only-not-approved-genesis"
    assert payload["does_not_generate_genesis"] is True


def test_m4_runner_source_profile_is_wired() -> None:
    proc = run(sys.executable, "tools/run_m4_release_candidate.py", "--profile", "source", "--dry-run", "--no-write")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert any("check_m4_readiness.py" in command for command in payload["commands"])


def test_m4_docs_include_no_overclaim_language() -> None:
    docs = [
        "docs/M4_MAINNET_READY.md",
        "docs/MAINNET_GOVERNANCE_LEGAL_RUNBOOK.md",
        "docs/M4_VERSION_BITS_AND_CHECKPOINT_SIGNOFF.md",
        "docs/MAINNET_GENESIS_DISTRIBUTION_PROPOSAL.md",
    ]
    joined = "\n".join((ROOT / path).read_text() for path in docs)
    assert "Do **not** claim" in joined
    assert "not legal advice" in joined
    assert "blocked-by-consensus-signoff" in joined
    assert "not an approved genesis allocation" in joined
