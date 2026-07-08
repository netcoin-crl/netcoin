from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.apps.markets.integrity import (
    cancel_rate_report,
    dispute_timeline,
    market_integrity_score,
    self_trade_report,
)
from netcoin.exchange_reserves import (
    LiabilityMerkleTree,
    reserve_attestation,
    verify_liability_proof,
    verify_reserve_attestation,
)
from netcoin.explorer_watch import ExplorerWatchStore
from netcoin.indexer_storage import IndexerStorage
from netcoin.ops_runbooks import diagnostic_bundle, recommended_actions, write_diagnostic_bundle
from netcoin.wallet_approvals import WalletApprovalQueue


def _seed_indexer(path: Path) -> IndexerStorage:
    storage = IndexerStorage(path)
    with storage.connect() as conn:
        conn.execute(
            "INSERT INTO blocks(height,block_hash,previous_hash,timestamp,tx_count,weight) VALUES(7,'block777','block666',1700000000,1,400)"
        )
        conn.execute(
            "INSERT INTO transactions(txid,block_hash,height,position,timestamp,input_sats,output_sats,fee_sats,raw_json,mempool) VALUES('tx777','block777',7,0,1700000000,0,5000,0,'{}',0)"
        )
        conn.execute(
            "INSERT INTO address_events(address,txid,block_hash,height,vout,direction,amount_sats,timestamp,coinbase,spent_outpoint) VALUES('netwatch','tx777','block777',7,0,'receive',5000,1700000000,0,'')"
        )
        conn.commit()
    return storage


def test_explorer_watchlist_scans_indexer_and_deduplicates(tmp_path: Path):
    storage = _seed_indexer(tmp_path / "indexer.sqlite")
    watches = ExplorerWatchStore(tmp_path / "watch.sqlite")
    addr_watch = watches.add_watch("address", "netwatch", label="cold wallet")
    watches.add_watch("transaction", "tx777")
    watches.add_watch("block", "7")
    result = watches.scan_indexer(storage)
    assert result["new_notifications"] == 3
    assert watches.scan_indexer(storage)["new_notifications"] == 0
    notes = watches.notifications(unseen_only=True)
    assert {n["kind"] for n in notes} == {"address_activity", "transaction_seen", "block_seen"}
    assert watches.summary()["active_watches"]["address"] == 1
    seen = watches.mark_seen([notes[0]["notification_id"]])
    assert seen["updated"] >= 0
    assert watches.deactivate_watch(addr_watch["item_id"])["active"] is False


def test_wallet_approval_queue_blocks_and_approves(tmp_path: Path):
    preview = {
        "txid": "tx-safe",
        "fee_sats": 1000,
        "output_sats": 50_000,
        "risk_score": 0,
        "risk_level": "low",
        "warnings": [],
        "inputs": [{"outpoint": "a:0"}],
        "recipient_outputs": [{"address": "netx", "amount_sats": 50_000}],
    }
    queue = WalletApprovalQueue(tmp_path / "approvals.sqlite")
    req = queue.create_request("wallet-1", preview, profile="standard", requester="browser")
    assert req["status"] == "pending"
    approved = queue.approve(req["request_hash"], approver="alice")
    assert approved["status"] == "approved"
    assert approved["receipt"]["approved"] is True
    assert queue.summary()["counts"]["approved"] == 1

    risky = dict(
        preview, txid="tx-risk", fee_sats=99_000_000, risk_level="critical", warnings=[{"severity": "critical"}]
    )
    blocked = queue.create_request("wallet-1", risky, profile="starter")
    assert blocked["status"] == "blocked"


def test_ops_runbook_bundle_redacts_and_suggests_actions(tmp_path: Path):
    alerts = [{"alert": "NetCoinNoPeers", "severity": "critical", "message": "no peers"}]
    actions = recommended_actions(alerts)
    assert actions["action_count"] >= 1
    bundle = diagnostic_bundle(metrics={"api_key": "secret", "netcoin_peer_count": 0}, alerts=alerts)
    assert bundle["status"] == "critical"
    assert bundle["metrics"]["api_key"] == "[REDACTED]"
    out = write_diagnostic_bundle(tmp_path / "bundle.json", metrics={"password": "pw"}, alerts=alerts)
    assert out["ok"] is True
    saved = json.loads((tmp_path / "bundle.json").read_text())
    assert saved["metrics"]["password"] == "[REDACTED]"


def test_market_integrity_reports_self_trade_cancel_rate_and_timeline():
    market = {
        "market_id": "m1",
        "status": "resolved",
        "winning_outcome_id": "YES",
        "trades": [{"trade_id": "t1", "maker": "demo:a", "taker": "demo:a"}],
        "orders": [{"trader_address": "demo:a", "status": "canceled"} for _ in range(5)]
        + [{"trader_address": "demo:b", "status": "filled"}],
        "resolution_evidence": [{"title": "Result", "timestamp": 10}],
        "disputes": [{"comment": "bad source", "created_at": 20}],
        "audit_trail": [{"event": "resolve_market", "created_at": 30}],
    }
    assert self_trade_report(market)["flagged_count"] == 1
    assert cancel_rate_report(market)["flagged_count"] == 1
    timeline = dispute_timeline(market)
    assert timeline["event_count"] == 3
    score = market_integrity_score(market)
    assert score["risk_level"] in {"medium", "high", "critical"}
    assert "self_trading_detected" in score["penalties"]


def test_exchange_reserve_merkle_proofs_and_attestation():
    liabilities = [
        {"customer_id": "alice", "amount_sats": 1000, "nonce": "a"},
        {"customer_id": "bob", "amount_sats": 2000, "nonce": "b"},
        {"customer_id": "carol", "amount_sats": 500, "nonce": "c"},
    ]
    tree = LiabilityMerkleTree(liabilities)
    proof = tree.proof_for_customer("bob")
    assert proof["found"] is True
    assert verify_liability_proof("bob", 2000, "b", proof["proof"], proof["root"]) is True
    assert verify_liability_proof("bob", 1999, "b", proof["proof"], proof["root"]) is False
    attestation = reserve_attestation(
        liabilities=liabilities, reserves=[{"address": "netreserve", "amount_sats": 4000}], operator="unit"
    )
    assert attestation["solvent"] is True
    assert verify_reserve_attestation(attestation)["ok"] is True
    tampered = dict(attestation, total_reserves_sats=1)
    assert verify_reserve_attestation(tampered)["ok"] is False


def test_new_tools_run_directly(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    bundle = tmp_path / "ops.json"
    result = subprocess.check_output(
        [sys.executable, "tools/generate_ops_bundle.py", "--out", str(bundle)], cwd=root, text=True
    )
    assert json.loads(result)["ok"] is True
    liabilities = tmp_path / "liabilities.json"
    reserves = tmp_path / "reserves.json"
    liabilities.write_text(json.dumps([{"customer_id": "alice", "amount_sats": 1, "nonce": "n"}]))
    reserves.write_text(json.dumps([{"address": "netreserve", "amount_sats": 2}]))
    attestation = tmp_path / "attestation.json"
    result = subprocess.check_output(
        [
            sys.executable,
            "tools/generate_reserve_attestation.py",
            str(liabilities),
            str(reserves),
            "--out",
            str(attestation),
        ],
        cwd=root,
        text=True,
    )
    payload = json.loads(result)
    assert payload["ok"] is True
    assert payload["solvent"] is True
