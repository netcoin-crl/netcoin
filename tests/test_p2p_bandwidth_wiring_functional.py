"""Proof that bandwidth budgeting and p2p hardening are wired into runtime paths."""

import os

from netcoin.node import _p2p_hardening_snapshot
from netcoin.pex import build_pex_response


def _diverse_peers(n: int):
    # Distinct /8s so diversity grouping does not collapse them.
    return [{"host": f"{10 + i}.0.0.1", "port": 28444, "score": 100 - i, "services": ["NETCOIN_PEX"]} for i in range(n)]


def test_bandwidth_mode_caps_pex_advertisement():
    peers = _diverse_peers(20)
    normal = build_pex_response(peers, limit=1000)
    home = build_pex_response(peers, limit=1000, bandwidth_mode="home")
    low = build_pex_response(peers, limit=1000, bandwidth_mode="low")
    # home budget = 6 outbound peers, low = 4; normal is uncapped by mode.
    assert normal["count"] > home["count"] >= low["count"]
    assert home["count"] <= 6
    assert low["count"] <= 4


def test_p2p_getaddr_respects_bandwidth_env(monkeypatch):
    # The p2p handler reads NETCOIN_BANDWIDTH_MODE; prove the plumbing is live.
    from netcoin import p2p

    class FakePeerDB:
        def candidates(self, *, limit, include_banned, max_per_group):
            return _diverse_peers(20)[:limit]

    class FakeChain:
        peer_database = FakePeerDB()

    monkeypatch.setenv("NETCOIN_BANDWIDTH_MODE", "low")
    msg = p2p.handle_message(p2p.Message("getaddr", b""), chain=FakeChain())
    # addr_message wraps the records; decode count via the payload.
    import json as _json

    addresses = _json.loads(msg.payload.decode())["addresses"]
    assert len(addresses) <= 4


def test_p2p_hardening_endpoint_reports_live_capabilities():
    snap = _p2p_hardening_snapshot()
    assert snap["schema"]
    assert snap["pex_enabled"] is True
    assert snap["addrv2_enabled"] is True
    assert snap["compact_blocks_enabled"] is True
    assert "plan_hash" in snap
    # ok/issues are computed by the real validator (independent operators still needed).
    assert isinstance(snap["issues"], list)
