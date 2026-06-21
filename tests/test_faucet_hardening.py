"""Tests for the non-CAPTCHA faucet hardening: body cap, burst throttle,
abuse log, and the wallet-balance gate."""
import importlib.util
import time
from pathlib import Path


def load_faucet_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "faucet_server.py"
    spec = importlib.util.spec_from_file_location("netcoin_faucet_server_hardening", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_body_too_large(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "MAX_BODY_BYTES", 100)
    assert faucet.body_too_large(101) is True
    assert faucet.body_too_large(100) is False
    assert faucet.body_too_large(0) is False


def test_burst_limited_counts_last_minute(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "MAX_REQUESTS_PER_MINUTE", 3)
    now = int(time.time())
    state = {"requests": [
        {"ip": "a", "timestamp": now - 5},
        {"ip": "b", "timestamp": now - 10},
        {"ip": "c", "timestamp": now - 70},  # older than 60s, doesn't count
    ]}
    assert faucet.burst_limited(state, now=now) is False  # only 2 in the last minute
    state["requests"].append({"ip": "d", "timestamp": now - 1})
    assert faucet.burst_limited(state, now=now) is True  # now 3 in the last minute


def test_record_abuse_appends_and_caps(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "MAX_ABUSE_LOG", 5)
    state: dict = {}
    for i in range(8):
        faucet.record_abuse(state, f"10.0.0.{i}", "invalid-address", now=1000 + i)
    log = state["abuse"]
    assert len(log) == 5  # capped
    # The newest entries are kept; the oldest are dropped.
    assert log[-1]["ip"] == "10.0.0.7"
    assert log[0]["ip"] == "10.0.0.3"
    assert log[0]["reason"] == "invalid-address"


def test_sufficient_funds_gate():
    faucet = load_faucet_module()
    # 5 NET + 0.01 NET fee = 5.01 NET = 501_000_000 sats
    assert faucet.sufficient_funds(501_000_000, "5", "0.01") is True
    assert faucet.sufficient_funds(500_999_999, "5", "0.01") is False
    # Unknown balance must not block (best-effort).
    assert faucet.sufficient_funds(None, "5", "0.01") is True
    # Malformed amounts default to not-blocking rather than crashing.
    assert faucet.sufficient_funds(0, "not-a-number", "0.01") is True
