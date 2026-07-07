from pathlib import Path

from netcoin.professional import build_release_manifest, issue_report, professional_readiness


def test_professional_readiness_core_controls_present():
    root = Path(__file__).resolve().parents[1]
    report = professional_readiness(root)
    assert report["score"] >= 90
    assert report["mainnet_safe"] is False
    names = {c["name"]: c for c in report["checks"]}
    assert names["api:idempotency"]["ok"]
    assert names["markets:surveillance"]["ok"]
    assert names["node:metrics"]["ok"]
    assert not report["open_high_severity"]


def test_issue_report_and_manifest_are_deterministic_enough():
    root = Path(__file__).resolve().parents[1]
    payload = issue_report(root)
    assert payload["protocol_vectors_ok"] is True
    assert payload["readiness_score"] >= 90
    manifest = build_release_manifest(root, include_files=["pyproject.toml", "README.md"])
    assert manifest["schema"] == "netcoin-release-manifest-v1"
    assert manifest["manifest_sha256"]
    assert {f["path"] for f in manifest["files"]} == {"pyproject.toml", "README.md"}
