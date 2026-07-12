import json
import subprocess
import sys
from pathlib import Path

from netcoin.hardware_wallet import (
    build_hardware_sign_request,
    stable_hash,
    validate_hardware_transcript,
)

ROOT = Path(__file__).resolve().parents[1]


def test_hardware_sign_request_contains_no_private_key_material():
    request = build_hardware_sign_request(
        "netpsbt:" + "00" * 8,
        device_family="Ledger Nano S Plus",
        transport="webhid",
        derivation_path="m/84'/0'/0'/0/0",
    )
    assert request["device_family"] == "ledger"
    assert request["transport"] == "webhid"
    assert request["private_key_material_included"] is False
    assert request["challenge"]
    assert request["request_hash"]


def test_hardware_transcript_validator_accepts_complete_evidence():
    body = {
        "schema": "netcoin-hardware-device-transcript-v1",
        "device_family": "ledger",
        "device_model": "Ledger Nano S Plus",
        "firmware_version": "test-firmware",
        "transport": "webhid",
        "network": "testnet",
        "derivation_path": "m/84'/0'/0'/0/0",
        "psbt_sha256": "a" * 64,
        "challenge": "b" * 64,
        "address_reviewed_on_device": True,
        "tx_reviewed_on_device": True,
        "fee_reviewed_on_device": True,
        "change_reviewed_on_device": True,
        "signed_psbt": "netpsbt:" + "11" * 8,
        "operator_attestation": "signed by test operator",
    }
    body["evidence_hash"] = stable_hash(body)
    assert validate_hardware_transcript(body) == []


def test_m2_manifest_and_public_security_pages_exist():
    manifest = json.loads((ROOT / "architecture/m2-trust-hardening.json").read_text())
    ids = {item["id"] for item in manifest["deliverables"]}
    assert "hardware-wallet-contract" in ids
    assert "fee-bumping" in ids
    assert "signed-releases-sbom-provenance" in ids
    assert "Bug bounty" in (ROOT / "sites/security/bug-bounty.html").read_text()
    assert "NetCoin release keys" in (ROOT / "sites/keys/index.html").read_text()


def test_m2_readiness_source_gate_passes():
    proc = subprocess.run(
        [sys.executable, "tools/check_m2_readiness.py", "--out", "reports/m2_readiness_source_report.json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads((ROOT / "reports/m2_readiness_source_report.json").read_text())
    assert report["ok"] is True
    assert report["claim_level"] == "m2-source-complete-evidence-required"


def test_reproducible_build_and_slsa_tools_source_run():
    for command in (
        [
            sys.executable,
            "tools/verify_reproducible_build.py",
            "--out",
            "reports/reproducible_build_source_report.json",
        ],
        [sys.executable, "tools/generate_sbom.py", "--out", "dist/netcoin-sbom.json"],
        [
            sys.executable,
            "tools/generate_slsa_provenance.py",
            "--subject",
            "dist/netcoin-sbom.json",
            "--out",
            "dist/netcoin-slsa-provenance.json",
        ],
    ):
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
