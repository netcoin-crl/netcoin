from __future__ import annotations

import json
from pathlib import Path

from netcoin.proof_triage import (
    build_proof_triage_report,
    check_ci_alignment,
    load_proof_triage_manifest,
    proof_triage_summary,
    render_triage_markdown,
    validate_proof_triage_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_proof_triage_manifest_validates() -> None:
    manifest = load_proof_triage_manifest()
    assert manifest["version"] == "0.39.4"
    assert validate_proof_triage_manifest(manifest, root=ROOT) == []


def test_ci_alignment_is_checked() -> None:
    manifest = load_proof_triage_manifest()
    alignment = check_ci_alignment(manifest, root=ROOT)
    assert alignment["workflow"] == ".github/workflows/proof-hardening.yml"
    assert "python-source-proof" in alignment["required_jobs"]
    assert "release-readiness-scorecard" in alignment["required_jobs"]
    assert isinstance(alignment["missing_jobs"], list)


def test_triage_classifies_source_only_and_failures(tmp_path: Path) -> None:
    local_report = {
        "ok": True,
        "profile": "sandbox",
        "gates": [
            {"gate_id": "rust-parity", "status": "source_only", "remediation": "Run strict Rust parity."},
            {
                "gate_id": "typescript-api",
                "status": "fail",
                "remediation": "Run npm ci && npm run ci:api.",
                "commands": [{"returncode": 1, "stderr_tail": "error"}],
            },
        ],
    }
    evidence = {"ok": True, "gates": [], "blockers": []}
    local_path = tmp_path / "local.json"
    evidence_path = tmp_path / "evidence.json"
    local_path.write_text(json.dumps(local_report), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    manifest = load_proof_triage_manifest()
    report = build_proof_triage_report(
        manifest,
        root=ROOT,
        local_report_path=str(local_path),
        evidence_bundle_path=str(evidence_path),
    )
    assert report["ok"] is True
    classes = {item["class"] for item in report["items"]}
    assert "source-only-evidence" in classes
    assert "command-failure" in classes
    assert report["strict_ready"] is False
    summary = proof_triage_summary(report)
    assert summary["item_count"] >= 2


def test_triage_markdown_names_next_priority(tmp_path: Path) -> None:
    local_report = {
        "ok": False,
        "profile": "strict",
        "gates": [
            {
                "gate_id": "rust-workspace",
                "status": "blocked",
                "remediation": "Install Rust and rerun cargo test.",
                "commands": [{"blocked_reason": "required tool unavailable for strict proof: cargo"}],
            }
        ],
    }
    evidence = {"ok": True, "gates": [], "blockers": []}
    local_path = tmp_path / "local.json"
    evidence_path = tmp_path / "evidence.json"
    local_path.write_text(json.dumps(local_report), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    report = build_proof_triage_report(load_proof_triage_manifest(), root=ROOT, local_report_path=str(local_path), evidence_bundle_path=str(evidence_path))
    markdown = render_triage_markdown(report)
    assert "NetCoin Proof Triage Summary" in markdown
    assert "rust-workspace" in markdown
    assert "cargo test" in markdown
