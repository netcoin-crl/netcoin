from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from netcoin.competitive import COMPETITIVE_AREAS, build_level5_report, validate_level5, all_area_smokes
from netcoin.competitive.level5 import (
    LEVEL5_SCORE,
    MetricsRegistry,
    NonceStore,
    IdempotencyStore,
    advance_proposal_state,
    analyze_contract_source,
    atomic_write_json,
    backup_paths,
    deposit_status,
    disclosure_check,
    encrypt_wallet_payload,
    decrypt_wallet_payload,
    estimate_fee_rate,
    faucet_decision,
    index_blocks,
    market_integrity_scan,
    mempool_policy_check,
    peer_diversity_report,
    peer_score,
    pool_payouts,
    release_manifest,
    scoped_api_key_allows,
    security_issue_register,
    sign_payload,
    tally_votes,
    quality_matrix_status,
    verify_payload_signature,
    wallet_risk_score,
)

ROOT = Path(__file__).resolve().parents[1]


def test_every_feature_is_at_least_level5():
    report = build_level5_report()
    assert report["ok"] is True
    assert report["minimum_feature_score"] >= 5
    assert report["feature_count"] >= 170
    for area in report["areas"]:
        assert area["maturity_score"] >= 5
        assert area["production_ready"] is False
        for feature in area["features"]:
            assert feature["maturity_score"] >= 5
            assert feature["status"] == "midlevel_testnet"
            assert feature["production_ready"] is False


def test_level5_validation_and_smokes_pass():
    validation = validate_level5()
    assert validation["ok"] is True
    assert validation["minimum_feature_score"] == LEVEL5_SCORE
    smokes = all_area_smokes()
    assert smokes["ok"] is True
    assert set(smokes["areas"]) == {area.slug for area in COMPETITIVE_AREAS}


def test_each_area_module_exposes_midlevel_controls():
    for area in COMPETITIVE_AREAS:
        module = importlib.import_module(f"netcoin.competitive.{area.module}")
        controls = module.default_controls()
        assert controls["maturity_score"] == 5
        assert controls["production_ready"] is False
        assert controls["enabled_by_default"] is True
        assert all(row["maturity_score"] >= 5 for row in module.feature_matrix())
        assert module.smoke_check()["ok"] is True


def test_security_wallet_api_storage_level5_helpers(tmp_path):
    assert security_issue_register([])["ok"] is True
    vault = encrypt_wallet_payload({"address": "Nabc", "label": "test"}, "correct horse battery")
    assert decrypt_wallet_payload(vault, "correct horse battery")["address"] == "Nabc"
    with pytest.raises(ValueError):
        decrypt_wallet_payload(vault, "wrong passphrase")
    risk = wallet_risk_score({"outputs": [{"address": "N1", "amount": 1}], "fee": 2}, known_addresses=["N2"])
    assert "high_fee" in risk["warnings"]
    sig = sign_payload("secret", {"x": 1})
    assert verify_payload_signature("secret", {"x": 1}, sig)
    nonces = NonceStore()
    assert nonces.accept("alice", 1)
    assert not nonces.accept("alice", 1)
    idem = IdempotencyStore()
    assert idem.run("k", {"ok": True})[0] is True
    assert idem.run("k", {"ok": False})[1] == {"ok": True}
    assert scoped_api_key_allows({"scopes": ["market"]}, "market:create")
    out = tmp_path / "state.json"
    assert atomic_write_json(out, {"height": 1})["ok"] is True
    backup = backup_paths([out], tmp_path / "backup.zip")
    assert backup["ok"] is True


def test_network_mempool_mining_explorer_faucet_helpers():
    assert peer_score({"invalid_messages": 0, "successful_relays": 5}) >= 100
    assert peer_diversity_report([{"host": "1.1.1.1"}, {"host": "2.2.2.2"}])["ok"]
    fees = estimate_fee_rate([], [{"fee_sats": 500, "vbytes": 250}, {"fee_sats": 1000, "vbytes": 250}])
    assert fees["fast"] >= fees["normal"] >= fees["slow"]
    assert mempool_policy_check({"fee_sats": 500, "vbytes": 250, "outputs": [{"sats": 1000}]})["ok"]
    payouts = pool_payouts([{"miner": "a", "difficulty": 1}, {"miner": "b", "difficulty": 3}], 40)
    assert payouts["payouts"]["b"] > payouts["payouts"]["a"]
    index = index_blocks([{"height": 1, "transactions": [{"outputs": [{"address": "N1", "amount": 2}]}]}])
    assert index["balances"]["N1"] == 2
    assert faucet_decision({"ip": "1", "address": "N1", "captcha_ok": True}, [])["allow"]


def test_market_contract_governance_release_observability_exchange_product_testing_helpers(tmp_path):
    market = market_integrity_scan([{"trader": "a"} for _ in range(5)], [])
    assert market["ok"] is False
    assert analyze_contract_source("function safe() {}")["ok"] is True
    assert advance_proposal_state("draft", "submit") == "review"
    assert tally_votes([{"choice": "yes"}, {"choice": "no"}, {"choice": "yes"}], quorum=3)["accepted"]
    f = tmp_path / "artifact.txt"
    f.write_text("release")
    manifest = release_manifest([f])
    assert manifest["files"][0]["sha256"]
    metrics = MetricsRegistry()
    metrics.set("netcoin_height", 123)
    assert "netcoin_height 123.0" in metrics.prometheus_text()
    assert deposit_status(6)["confirmed"]
    assert disclosure_check({"home": "NetCoin is testnet educational no real value."})["ok"]
    assert quality_matrix_status([{"status": "pass"}, {"status": "pass"}])["coverage_percent"] == 100


def test_competitive_cli_and_tool_level5(tmp_path):
    out = tmp_path / "level5.json"
    subprocess.check_call([sys.executable, "tools/competitive_gap_report.py", "--level5", "--json", "--out", str(out)], cwd=ROOT)
    data = json.loads(out.read_text())
    assert data["schema"] == "netcoin-competitive-level5-v1"
    assert data["minimum_feature_score"] == 5
    subprocess.check_call([sys.executable, "-m", "netcoin.cli", "competitive-check", "--level5", "--validate", "--fail-on-issues"], cwd=ROOT)
