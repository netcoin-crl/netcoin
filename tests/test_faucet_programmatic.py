"""Programmatic faucet: API-key claims with per-key 24h quota (P11)."""

import importlib

import pytest

faucet = importlib.import_module("tools.faucet_server")


def test_api_key_quotas_parsing(monkeypatch):
    monkeypatch.setenv("NETCOIN_FAUCET_API_KEYS", "cikey_a:50, cikey_b:10 ,bad, cikey_c:x")
    quotas = faucet.api_key_quotas()
    assert quotas == {"cikey_a": 50, "cikey_b": 10}  # "bad" (no quota) and non-int dropped


def test_api_key_quotas_disabled_when_unset(monkeypatch):
    monkeypatch.delenv("NETCOIN_FAUCET_API_KEYS", raising=False)
    assert faucet.api_key_quotas() == {}


def test_authorize_rejects_missing_and_invalid_keys(monkeypatch):
    monkeypatch.setenv("NETCOIN_FAUCET_API_KEYS", "good:3")
    state = {}
    ok, reason, remaining = faucet.authorize_api_claim("", state)
    assert not ok and "missing" in reason
    ok, reason, remaining = faucet.authorize_api_claim("nope", state)
    assert not ok and "invalid" in reason and remaining == 0


def test_quota_is_enforced_over_24h(monkeypatch):
    monkeypatch.setenv("NETCOIN_FAUCET_API_KEYS", "ci:3")
    state = {}
    now = 1_000_000
    for i in range(3):
        ok, reason, remaining = faucet.authorize_api_claim("ci", state, now=now)
        assert ok, reason
        assert remaining == 3 - i
        faucet.record_api_claim("ci", state, now=now)
    # 4th claim within 24h is refused.
    ok, reason, remaining = faucet.authorize_api_claim("ci", state, now=now)
    assert not ok and "quota" in reason and remaining == 0
    # After the window rolls forward, the key is authorized again.
    ok, reason, remaining = faucet.authorize_api_claim("ci", state, now=now + 24 * 3600 + 1)
    assert ok and remaining == 3


def test_record_api_claim_prunes_old_stamps(monkeypatch):
    monkeypatch.setenv("NETCOIN_FAUCET_API_KEYS", "ci:5")
    state = {"api_claims": {"ci": [1, 2, 3]}}  # ancient stamps
    faucet.record_api_claim("ci", state, now=1_000_000)
    assert state["api_claims"]["ci"] == [1_000_000]  # old ones pruned
