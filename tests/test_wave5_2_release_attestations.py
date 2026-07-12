from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_planner():
    spec = importlib.util.spec_from_file_location(
        "plan_release_attestation_verification",
        ROOT / "tools" / "plan_release_attestation_verification.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_workflow_generates_github_artifact_attestations():
    workflow = read(".github/workflows/release.yml")
    assert "attestations: write" in workflow
    assert "actions/attest-build-provenance@v4" in workflow
    assert "NETCOIN_RELEASE_ARCHIVE" in workflow
    assert "subject-path: ${{ env.NETCOIN_RELEASE_ARCHIVE }}" in workflow
    assert "subject-path: dist/netcoin-sbom.json" in workflow
    assert "subject-path: dist/SHA256SUMS" in workflow


def test_attestation_verification_planner_lists_release_subjects(tmp_path: Path):
    planner = load_planner()
    dist = tmp_path / "dist"
    dist.mkdir()
    for name in ["netcoin-1.2.3.zip", "netcoin-sbom.json", "SHA256SUMS"]:
        (dist / name).write_text(name, encoding="utf-8")

    payload = planner.plan(dist, "netcoin/example")
    assert payload["ok"] is True
    assert payload["schema"] == "netcoin-release-attestation-verification-plan-v1"
    assert payload["does_not_verify_offline"] is True
    assert payload["commands"] == [
        f"gh attestation verify {dist / 'netcoin-1.2.3.zip'} -R netcoin/example",
        f"gh attestation verify {dist / 'netcoin-sbom.json'} -R netcoin/example",
        f"gh attestation verify {dist / 'SHA256SUMS'} -R netcoin/example",
    ]


def test_release_docs_explain_github_attestation_verification():
    docs = read("docs/REPRODUCIBLE_RELEASES.md") + "\n" + read("docs/RELEASING.md")
    assert "GitHub artifact attestations" in docs
    assert "tools/plan_release_attestation_verification.py" in docs
    assert "gh attestation verify" in docs
    assert "source archive, `netcoin-sbom.json`, and `SHA256SUMS`" in docs
