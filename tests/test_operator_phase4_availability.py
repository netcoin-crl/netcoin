from __future__ import annotations

import json
from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain
from netcoin.live_product import operator_live_controls

ROOT = Path(__file__).resolve().parents[1]


class DummyNode:
    self_url = "127.0.0.1:28444"
    advertise_unreachable = True
    advertise_unreachable_error = "self-dial failed"
    peer_manager = None

    def info(self):
        return {
            "advertise": self.self_url,
            "advertise_unreachable": self.advertise_unreachable,
            "advertise_unreachable_error": self.advertise_unreachable_error,
        }


def test_operator_live_payload_exposes_phase4_read_only_ops_status(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    status, payload, ctype = route_app_get(store, chain, "/api/operator/live", {}, node=DummyNode())

    assert status == 200
    assert ctype == "application/json"
    assert payload["chainstate"]["commitment"]
    assert payload["chainstate"]["height"] == chain.height()
    assert payload["ledger_audit"]["status"] == "missing-report"
    assert "run_ledger_audit.py" in payload["ledger_audit"]["command"]
    assert payload["peer_advertise"]["status"] == "unreachable"
    assert payload["peer_advertise"]["error"] == "self-dial failed"
    assert payload["maintenance"]["destructive_actions_enabled"] is False
    assert "reindex" in payload["maintenance"]["reindex_command"]
    assert "backup" in payload["maintenance"]["backup_command"]


def test_operator_live_payload_reads_latest_ledger_audit_report(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    reports = tmp_path / "repo" / "reports"
    reports.mkdir(parents=True)
    report = {
        "ok": True,
        "independent": {"accounts": [{"account": "asset:cash"}, {"account": "liability:customer:alice"}]},
        "mismatches": [],
    }
    (reports / "ledger_audit_report.json").write_text(json.dumps(report), encoding="utf-8")

    payload = operator_live_controls(chain, root=tmp_path / "repo")

    assert payload["ledger_audit"]["status"] == "available"
    assert payload["ledger_audit"]["ok"] is True
    assert payload["ledger_audit"]["rows_checked"] == 2
    assert payload["ledger_audit"]["drift_detected"] is False
    assert payload["ledger_audit"]["report_path"].endswith("ledger_audit_report.json")


def test_operator_dashboard_exposes_phase4_cards_without_destructive_buttons() -> None:
    html = (ROOT / "sites/operator/index.html").read_text(encoding="utf-8")
    js = (ROOT / "sites/operator/operator.js").read_text(encoding="utf-8")

    for marker in ["ledgerAudit", "chainstateHash", "peerAdvertise", "maintenance"]:
        assert marker in html
    for text in ["Ledger audit", "Chainstate hash", "Peer advertise health", "Backup and reindex"]:
        assert text in html
    for text in ["renderLedgerAudit", "renderChainstate", "renderAdvertise", "renderMaintenance"]:
        assert text in js
    assert "destructive browser actions stay disabled" in js
    assert "run_ledger_audit.py" in js
    assert "operator.css?v=20260717-minilist-grid" in html
    assert "operator.js?v=20260722-payout-panel" in html
