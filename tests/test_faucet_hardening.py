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


def test_client_ip_ignores_forwarded_header_unless_trusted(monkeypatch):
    faucet = load_faucet_module()

    class Handler:
        headers = {"X-Forwarded-For": "203.0.113.55"}
        client_address = ("127.0.0.1", 12345)

    monkeypatch.setattr(faucet, "TRUST_PROXY_HEADERS", False)
    assert faucet.client_ip(Handler()) == "127.0.0.1"

    monkeypatch.setattr(faucet, "TRUST_PROXY_HEADERS", True)
    assert faucet.client_ip(Handler()) == "203.0.113.55"


def test_request_content_length_rejects_malformed_value():
    faucet = load_faucet_module()

    class Handler:
        headers = {"Content-Length": "not-a-number"}

    assert faucet.request_content_length(Handler()) == -1


def test_burst_limited_counts_last_minute(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "MAX_REQUESTS_PER_MINUTE", 3)
    now = int(time.time())
    state = {
        "requests": [
            {"ip": "a", "timestamp": now - 5},
            {"ip": "b", "timestamp": now - 10},
            {"ip": "c", "timestamp": now - 70},  # older than 60s, doesn't count
        ]
    }
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


def test_public_queue_excludes_ips():
    faucet = load_faucet_module()
    state = {
        "queue": [
            {
                "id": "1",
                "ip": "203.0.113.10",
                "address": "Naddr",
                "amount": "5",
                "status": "queued",
                "timestamp": 1000,
            }
        ]
    }
    public = faucet.public_queue(state)
    assert public == [
        {
            "id": "1",
            "address": "Naddr",
            "amount": "5",
            "status": "queued",
            "txid": None,
            "timestamp": 1000,
            "updated_at": None,
        }
    ]
    assert "ip" not in public[0]


def test_queue_full_counts_pending_only(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "MAX_QUEUE_ITEMS", 2)
    state = {
        "queue": [
            {"status": "queued"},
            {"status": "sent"},
            {"status": "queued"},
        ]
    }
    assert faucet.queue_full(state) is True
    state["queue"][0]["status"] = "failed"
    assert faucet.queue_full(state) is False


def test_queued_request_rate_limits_same_ip(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "COOLDOWN_SECONDS", 60)
    now = int(time.time())
    monkeypatch.setattr(faucet.time, "time", lambda: now)
    state = {"requests": [], "queue": [{"ip": "203.0.113.10", "timestamp": now - 5, "status": "queued"}]}
    limited, remaining = faucet.rate_limited("203.0.113.10", state)
    assert limited is True
    assert remaining == 55
    other_limited, _ = faucet.rate_limited("203.0.113.11", state)
    assert other_limited is False


def test_process_queue_marks_sent_and_records_request(monkeypatch):
    faucet = load_faucet_module()
    state = {"requests": [], "queue": []}
    grant = faucet.queue_grant(state, "203.0.113.10", "Naddr", now=1000)
    monkeypatch.setattr(faucet, "faucet_spendable_sats", lambda: 1_000_000_000)
    monkeypatch.setattr(faucet, "send_faucet", lambda address: {"txid": f"tx-{address}"})
    result = faucet.process_queue(state, limit=1)
    assert result == {"processed": 1, "sent": 1, "failed": 0, "errors": []}
    assert grant["status"] == "sent"
    assert grant["txid"] == "tx-Naddr"
    assert state["requests"][0]["ip"] == "203.0.113.10"
    assert state["requests"][0]["txid"] == "tx-Naddr"


def test_process_queue_pauses_when_wallet_needs_refill(monkeypatch):
    faucet = load_faucet_module()
    state = {"requests": [], "queue": [{"id": "1", "address": "Naddr", "status": "queued", "timestamp": 1000}]}
    monkeypatch.setattr(faucet, "faucet_spendable_sats", lambda: 1)
    result = faucet.process_queue(state, limit=1)
    assert result["sent"] == 0
    assert result["errors"] == [{"id": "1", "error": "insufficient-funds"}]
    assert state["queue"][0]["status"] == "queued"


def test_hot_wallet_status_refill_signal(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "MIN_SPENDABLE_SATS", 1_000)
    monkeypatch.setattr(faucet, "REFILL_ADDRESS", "Nrefill")
    assert faucet.hot_wallet_status(None)["state"] == "unknown"
    low = faucet.hot_wallet_status(999)
    assert low["state"] == "needs_refill"
    assert low["refill_address"] == "Nrefill"
    assert faucet.hot_wallet_status(1000)["state"] == "ok"


def test_send_faucet_uses_configured_source_dir(monkeypatch):
    faucet = load_faucet_module()
    seen = {}

    class Result:
        returncode = 0
        stdout = '{"txid":"abc"}'
        stderr = ""

    def fake_run(command, cwd, text, capture_output, timeout):
        seen["command"] = command
        seen["cwd"] = cwd
        seen["text"] = text
        seen["capture_output"] = capture_output
        seen["timeout"] = timeout
        return Result()

    monkeypatch.setattr(faucet, "NETCOIN_SOURCE_DIR", Path("/srv/netcoin"))
    monkeypatch.setattr(faucet.subprocess, "run", fake_run)

    assert faucet.send_faucet("Naddr") == {"txid": "abc"}
    assert seen["cwd"] == "/srv/netcoin"
    assert seen["command"][0] == faucet.PYTHON
    assert seen["text"] is True
    assert seen["capture_output"] is True
    assert seen["timeout"] == 30
