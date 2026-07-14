import importlib.util
import json
import time
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.explorer_server import events_payload
from netcoin.node import NetCoinNode

ROOT = Path(__file__).resolve().parents[1]


def load_faucet_module():
    path = ROOT / "tools" / "faucet_server.py"
    spec = importlib.util.spec_from_file_location("netcoin_faucet_server_p12", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_explorer_has_pagination_csv_and_reorg_watch():
    html = (ROOT / "sites" / "explorer" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "sites" / "explorer" / "explorer-app.js").read_text(encoding="utf-8")
    assert "Reorg watch" in html
    for token in [
        "csvDataUri",
        "Export visible CSV",
        "offset=${nextOffset}",
        "Reorg / orphan watch",
        "/events?limit=50",
        "Export headers CSV",
    ]:
        assert token in js


def test_faucet_pow_autoscaling_and_admin_audit(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "POW_AUTOSCALE_ENABLED", True)
    monkeypatch.setattr(faucet, "POW_MAX_DIFFICULTY", 6)
    monkeypatch.setattr(faucet, "MAX_QUEUE_ITEMS", 10)
    now = int(time.time())
    state = {
        "difficulty": 2,
        "abuse": [{"timestamp": now - 10, "reason": "pow-failed"} for _ in range(6)],
        "queue": [{"status": "queued"} for _ in range(8)],
    }
    policy = faucet.autoscaled_pow_difficulty(state, now=now)
    assert policy["difficulty"] == 4
    assert policy["autoscaled"] is True
    assert any(reason.startswith("abuse_1h") for reason in policy["reasons"])
    assert any(reason.startswith("queue_pressure") for reason in policy["reasons"])

    entry = faucet.record_admin_audit(state, "config", actor="127.0.0.1", details={"difficulty": 3}, now=now)
    assert entry in state["admin_audit"]
    public = faucet.admin_audit_log(state)
    assert public[0]["action"] == "config"


def test_status_site_records_browser_uptime_history():
    html = (ROOT / "sites" / "status" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "sites" / "status" / "status.js").read_text(encoding="utf-8")
    assert "Uptime history" in html
    for token in ["UPTIME_HISTORY_KEY", "recordUptimeSample", "renderUptimeHistory", "last 288 checks"]:
        assert token in js


def test_metrics_are_documented_and_grafana_dashboard_is_importable(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "chain"), persist=False)
    metrics = node.metrics_text()
    for token in [
        "# TYPE netcoin_block_height gauge",
        "netcoin_chain_tip_info",
        "netcoin_mempool_bytes",
        "netcoin_build_info",
    ]:
        assert token in metrics

    docs = (ROOT / "docs" / "operations" / "prometheus_metrics.md").read_text(encoding="utf-8")
    assert "netcoin_mempool_bytes" in docs
    dashboard = json.loads((ROOT / "ops" / "grafana" / "netcoin-node-dashboard.json").read_text(encoding="utf-8"))
    assert dashboard["uid"] == "netcoin-node"
    assert any(panel["title"] == "Orphan Candidates" for panel in dashboard["panels"])


def test_explorer_server_events_payload_reports_orphan_candidates(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    assert events_payload(chain) == {
        "events": [],
        "orphan_candidates": 0,
        "source": "explorer-server-chain-state",
    }
