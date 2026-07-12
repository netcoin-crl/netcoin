from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "sites" / "status"


def test_status_page_exposes_m1_network_snapshot_card() -> None:
    html = (STATUS / "index.html").read_text(encoding="utf-8")
    assert "Live testnet snapshot" in html
    for token in [
        "statusHeight",
        "statusMempool",
        "statusPeers",
        "statusUptime",
        "networkState",
    ]:
        assert token in html
    assert "status.js?v=20260711-m1-network-snapshot" in html
    assert "status.css?v=20260711-m1-network-snapshot" in html


def test_status_js_reads_health_latest_mempool_and_peers() -> None:
    js = (STATUS / "status.js").read_text(encoding="utf-8")
    for endpoint in [
        "/api/health",
        "/api/latest?n=1",
        "/api/mempool?transactions=0",
        "/api/peers",
    ]:
        assert endpoint in js
    for token in [
        "function renderNetworkSnapshot",
        "function formatDuration",
        "Node reachable",
        "mempoolDepth",
        "peerCount",
        "uptime_seconds",
    ]:
        assert token in js


def test_static_status_api_fallbacks_exist_for_local_browser_runs() -> None:
    for rel in ["api/health", "api/latest", "api/mempool", "api/peers"]:
        path = ROOT / rel
        assert path.exists(), rel
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["status"] == "source-fallback"
