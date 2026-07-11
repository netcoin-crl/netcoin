from __future__ import annotations

import json
import tempfile
from pathlib import Path

from netcoin.captcha_provider import load_captcha_config, source_validation
from netcoin.custody_production import source_custody_smoke
from netcoin.incident_history import validate_incident_history
from netcoin.mainnet_readiness import load_manifest, stable_hash_json, strict_evidence_gate, validate_manifest


def test_mainnet_readiness_manifest_has_all_required_gates() -> None:
    manifest = load_manifest()
    issues = validate_manifest(manifest)
    assert issues == []
    gate_ids = {gate["id"] for gate in manifest["gates"]}
    assert "hardware-wallet-device-testing" in gate_ids
    assert "captcha-provider-integration" in gate_ids
    assert "production-exchange-custody" in gate_ids
    assert "external-crypto-security-audit" in gate_ids
    assert "public-production-p2p-soak" in gate_ids
    assert "long-python-suite-confidence" in gate_ids
    assert "mainnet-launch-checklist-approval" in gate_ids
    assert "public-testnet-incident-history" in gate_ids


def test_strict_evidence_gate_requires_hash_and_required_fields(tmp_path: Path) -> None:
    evidence = {
        "gate_id": "hardware-wallet-device-testing",
        "ok": True,
        "device_model": "test-device",
        "firmware_version": "1.0",
        "transport": "usb-hid",
        "address_reviewed_on_device": True,
        "tx_reviewed_on_device": True,
        "challenge_signature_verified": True,
        "operator_attestation": "signed by test operator",
    }
    evidence["evidence_hash"] = stable_hash_json(evidence)
    path = tmp_path / "hardware.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    result = strict_evidence_gate(
        "hardware-wallet-device-testing",
        path,
        [
            "device_model",
            "firmware_version",
            "transport",
            "address_reviewed_on_device",
            "tx_reviewed_on_device",
            "challenge_signature_verified",
            "operator_attestation",
        ],
    )
    assert result.ok


def test_captcha_source_validation_and_env_config() -> None:
    assert source_validation()["ok"] is True
    cfg = load_captcha_config({"NETCOIN_CAPTCHA_PROVIDER": "turnstile", "NETCOIN_CAPTCHA_SECRET": "secret"})
    assert cfg.configured
    assert "turnstile" in cfg.verify_url


def test_source_custody_smoke_balances_ledger() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = source_custody_smoke(Path(tmp) / "ledger.sqlite")
    assert result["ok"] is True
    assert result["balanced_double_entry_ledger"] is True
    assert result["hot_wallet_reconciliation"]["ok"] is True
    assert result["reserve_attestation_ok"] is True


def test_incident_history_accepts_no_incident_attestation() -> None:
    payload = {
        "public_testnet_start": "2026-07-01T00:00:00Z",
        "runbook_links": ["ops/runbooks/COMPETITIVE_OPERATIONS.md"],
        "no_incident_attestation": "No public incidents observed during this window.",
    }
    assert validate_incident_history(payload) == []
