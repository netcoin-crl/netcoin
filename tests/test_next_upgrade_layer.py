from __future__ import annotations

import csv
import io

from netcoin.apps.markets.governance import create_oracle_vote, dispute_escalation_plan, tally_oracle_votes
from netcoin.exchange_accounting import AccountingLedger, reconcile_hot_wallet
from netcoin.indexer_insights import (
    address_activity_heatmap,
    address_counterparties,
    export_address_history_csv,
    search_suggestions,
)
from netcoin.indexer_storage import IndexerStorage
from netcoin.ops_incidents import IncidentStore, runbook_for_alert
from netcoin.wallet_policy import approval_receipt, approval_request, evaluate_with_profile, verify_approval_receipt


def _seed_indexer(path):
    storage = IndexerStorage(path)
    with storage.connect() as conn:
        conn.execute(
            "INSERT INTO blocks(height,block_hash,previous_hash,timestamp,tx_count,weight) VALUES(1,'abcblock','genesis',1700000000,1,400)"
        )
        conn.execute(
            "INSERT INTO transactions(txid,block_hash,height,position,timestamp,input_sats,output_sats,fee_sats,raw_json,mempool) VALUES('abctx','abcblock',1,0,1700000000,0,1000,0,'{}',0)"
        )
        conn.execute(
            "INSERT INTO address_events(address,txid,block_hash,height,vout,direction,amount_sats,timestamp,coinbase,spent_outpoint) VALUES('neta111','abctx','abcblock',1,0,'receive',1000,1700000000,0,'')"
        )
        conn.execute(
            "INSERT INTO address_events(address,txid,block_hash,height,vout,direction,amount_sats,timestamp,coinbase,spent_outpoint) VALUES('netb222','abctx','abcblock',1,0,'send',-1000,1700000000,0,'old:0')"
        )
        conn.commit()
    return storage


class _Indexer:
    def __init__(self, storage):
        self.storage = storage

    def address_history(self, address, limit=100):
        rows = self.storage.rows("SELECT * FROM address_events WHERE address=? LIMIT ?", (address, limit))
        for row in rows:
            row["amount"] = str(row["amount_sats"])
        return {"address": address, "events": rows}


def test_indexer_insights_search_heatmap_counterparties_and_csv(tmp_path):
    storage = _seed_indexer(tmp_path / "idx.sqlite")
    indexer = _Indexer(storage)
    suggestions = search_suggestions(storage, "abc")
    assert {item["type"] for item in suggestions["suggestions"]} >= {"block", "transaction"}
    assert search_suggestions(storage, "1")["suggestions"][0]["type"] == "block"
    heatmap = address_activity_heatmap(storage, "neta111")
    assert heatmap["event_count"] == 1
    counterparties = address_counterparties(storage, "neta111")
    assert counterparties["counterparties"][0]["address"] == "netb222"
    csv_text = export_address_history_csv(indexer, "neta111")
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert rows[0]["txid"] == "abctx"


def test_wallet_policy_approval_receipts():
    preview = {
        "txid": "tx123",
        "fee_sats": 2000,
        "output_sats": 50_000,
        "risk_score": 0,
        "risk_level": "low",
        "warnings": [],
        "inputs": [{"outpoint": "a:0"}],
        "recipient_outputs": [{"address": "netx", "amount_sats": 50_000}],
    }
    decision = evaluate_with_profile(preview, "starter")
    assert decision["action"] == "allow"
    request = approval_request(preview, "starter", requester="unit-test")
    receipt = approval_receipt(request, approver="alice", approved=True)
    assert verify_approval_receipt(request, receipt)["ok"] is True
    risky = dict(preview, fee_sats=99_999_999, risk_level="critical", warnings=[{"severity": "critical"}])
    assert evaluate_with_profile(risky, "starter")["action"] == "block"


def test_ops_incident_store_ack_resolve_and_runbook(tmp_path):
    store = IncidentStore(tmp_path / "incidents.sqlite")
    result = store.ingest_alerts([{"alert": "NetCoinNoPeers", "severity": "warning", "message": "no peers"}])
    assert result["opened"] == 1
    incident = store.list()[0]
    assert "verify seed nodes" in incident["runbook"]
    ack = store.acknowledge(incident["incident_id"], "operator")
    assert ack["status"] == "acknowledged"
    resolved = store.resolve(incident["incident_id"])
    assert resolved["status"] == "resolved"
    assert runbook_for_alert("Unknown")["steps"]


def test_market_governance_quorum_and_dispute_plan():
    evidence = {"url": "https://example.invalid/result", "title": "result"}
    votes = [create_oracle_vote(f"oracle-{i}", "m1", "yes", evidence, confidence_bps=9000) for i in range(3)]
    tally = tally_oracle_votes(votes, quorum=3)
    assert tally["ready"] is True
    assert tally["winning_outcome_id"] == "yes"
    plan = dispute_escalation_plan({"market_id": "m1", "state": "resolved"}, [{"reason": "bad source"}], votes)
    assert plan["severity"] == "critical"
    assert "freeze_claims_until_operator_review" in plan["actions"]


def test_exchange_accounting_balances_and_hot_wallet_reconciliation(tmp_path):
    ledger = AccountingLedger(tmp_path / "acct.sqlite")
    ledger.post_customer_deposit(customer_id="cust1", amount_sats=5000, deposit_id="dep1")
    ledger.post_customer_withdrawal(customer_id="cust1", amount_sats=1200, withdrawal_id="wd1")
    balances = ledger.account_balances()
    assert balances["balanced"] is True
    hot = next(row for row in balances["accounts"] if row["account"] == "asset:hot_wallet")
    assert hot["balance_sats"] == 3800
    assert reconcile_hot_wallet(ledger, observed_hot_wallet_sats=3800)["ok"] is True
    assert reconcile_hot_wallet(ledger, observed_hot_wallet_sats=3000)["delta_sats"] == -800
