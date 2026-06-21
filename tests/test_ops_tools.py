"""Tests for ops tooling: faucet admin dashboard render and monitor alerting."""
import importlib.util
from pathlib import Path


def load_tool(filename: str, modname: str):
    path = Path(__file__).resolve().parents[1] / "tools" / filename
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_faucet_admin_renders_requests_and_abuse():
    admin = load_tool("faucet_admin.py", "netcoin_faucet_admin")
    state = {
        "requests": [
            {"ip": "203.0.113.5", "address": "Nabc", "timestamp": 1718900000, "txid": "deadbeef", "amount": "5"},
        ],
        "abuse": [
            {"ip": "203.0.113.9", "reason": "rate-limited", "timestamp": 1718900100},
            {"ip": "203.0.113.9", "reason": "burst", "timestamp": 1718900200},
        ],
    }
    html = admin.render_faucet_admin(state, spendable_sats=501_000_000)
    assert "NetCoin Faucet Admin" in html
    assert "5.01000000 NET" in html  # 501_000_000 sats
    assert "deadbeef" in html and "203.0.113.5" in html
    assert "rate-limited" in html and "burst" in html


def test_faucet_admin_escapes_and_handles_empty():
    admin = load_tool("faucet_admin.py", "netcoin_faucet_admin2")
    html = admin.render_faucet_admin({"requests": [{"ip": "<b>x</b>", "address": "", "timestamp": "bad"}]})
    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    # unknown balance and a bad timestamp do not crash rendering
    assert "unknown" in html


def test_monitor_alerts_only_on_transitions():
    mon = load_tool("monitor_netcoin.py", "netcoin_monitor")
    prev = {"targets": {"seed1": {"ok": True}, "faucet": {"ok": True}}, "seed_tips_match": True}
    status = {
        "targets": {"seed1": {"ok": True}, "faucet": {"ok": False, "url": "http://x/faucet", "error": "timeout"}},
        "seed_tips_match": True,
    }
    alerts = mon.compute_alerts(status, prev)
    assert any("DOWN: faucet" in a for a in alerts)
    assert not any("seed1" in a for a in alerts)  # seed1 unchanged -> no alert


def test_monitor_alerts_recovery_and_tip_divergence():
    mon = load_tool("monitor_netcoin.py", "netcoin_monitor2")
    prev = {"targets": {"seed2": {"ok": False}}, "seed_tips_match": True}
    status = {"targets": {"seed2": {"ok": True}}, "seed_tips_match": False}
    alerts = mon.compute_alerts(status, prev)
    assert any("RECOVERED: seed2" in a for a in alerts)
    assert any("diverged" in a for a in alerts)


def test_monitor_send_alerts_is_noop_without_webhook():
    mon = load_tool("monitor_netcoin.py", "netcoin_monitor3")
    assert mon.send_alerts(["DOWN: seed1"], webhook=None) == 0
    assert mon.send_alerts([], webhook="http://example.invalid/hook") == 0
