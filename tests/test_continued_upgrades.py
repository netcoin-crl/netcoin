import json
import subprocess
import sys
import time
from pathlib import Path

from netcoin.apps.markets.mm import inventory_risk, rebalance_suggestions
from netcoin.apps.markets.oracles import OracleRegistry
from netcoin.apps.markets.reconciliation import settlement_audit_report
from netcoin.exchange import ExchangeLedger
from netcoin.indexer import ChainIndexer
from netcoin.metrics import MetricsHistory, service_health
from netcoin.peerdb import PeerDatabase
from netcoin.recovery import export_recovery_report, recovery_action_plan
from netcoin.sync import HeaderSyncScheduler
from netcoin.tx import Transaction, TxInput, TxOutput
from netcoin.tx_simulator import simulate_transaction
from netcoin.wallet import Wallet
from netcoin.wallet_risk import policy_decision, safety_report, sign_safety_report


class FakeChain:
    def __init__(self):
        self.known = set()

    def validate_headers_from_tip(self, headers):
        for h in headers:
            assert h["height"] >= 0

    def get_block_by_hash(self, h):
        return h if h in self.known else None


class FakeSpendable:
    def __init__(self, output):
        self.output = output


class FakeTxChain:
    def __init__(self, utxos):
        self._utxos = utxos

    def utxo_set(self):
        return self._utxos


def test_indexer_rich_address_profile_and_integrity(tmp_path):
    idx = ChainIndexer(tmp_path / "idx.sqlite")
    with idx.storage.connect() as conn:
        conn.execute(
            "INSERT INTO blocks(height,block_hash,previous_hash,timestamp,tx_count,weight) VALUES(1,'b1','b0',100,1,400)"
        )
        conn.execute(
            "INSERT INTO transactions(txid,block_hash,height,position,timestamp,input_sats,output_sats,fee_sats,raw_json,mempool) VALUES('t1','b1',1,0,100,0,1000,0,'{}',0)"
        )
        conn.execute(
            "INSERT INTO address_events(address,txid,block_hash,height,vout,direction,amount_sats,timestamp,coinbase,spent_outpoint) VALUES('n1abc','t1','b1',1,0,'receive',1000,100,0,'')"
        )
        conn.commit()
    profile = idx.address_profile("n1abc")
    assert profile["balance_sats"] == 1000
    assert profile["first_seen_height"] == 1
    assert idx.top_addresses()["addresses"][0]["address"] == "n1abc"
    assert idx.mempool_summary()["transaction_count"] == 0
    assert idx.integrity_report()["ok"] is True
    csv_report = idx.export_address_history_csv("n1abc", tmp_path / "history.csv")
    assert csv_report["rows"] == 1
    assert (tmp_path / "history.csv").read_text().startswith("id,address,txid")


def test_wallet_safety_report_policy_and_signature():
    wallet = Wallet.create()
    tx = Transaction(inputs=[TxInput(txid="1" * 64, vout=0)], outputs=[TxOutput(amount=1000, address=wallet.address)])
    preview = simulate_transaction(
        FakeTxChain({"1" * 64 + ":0": FakeSpendable(TxOutput(amount=500_000, address=wallet.address))}),
        tx,
        wallet_addresses={wallet.address},
        high_fee_bps=10,
    )
    decision = policy_decision(preview, max_fee_sats=100)
    assert decision["action"] == "block"
    report = safety_report(preview, policy={"max_fee_sats": 100})
    signed = sign_safety_report(report, wallet)
    assert signed["signer_address"] == wallet.address
    assert signed["signature"]


def test_recovery_action_plan_export(tmp_path):
    report = {"ok": False, "checks": [{"name": "seed_phrase", "ok": False}], "seed_backup": {"valid": False}}
    plan = recovery_action_plan(report)
    assert plan["actions"][0]["priority"] == "critical"
    out = export_recovery_report(tmp_path / "recovery.json", report)
    assert out["ok"] is True
    payload = json.loads((tmp_path / "recovery.json").read_text())
    assert payload["action_plan"]["action_count"] >= 1


def test_peerdb_health_prune_and_selection(tmp_path):
    db = PeerDatabase(tmp_path / "peers.sqlite")
    db.upsert_peer("http://10.0.0.1:28444", anchor=True, best_height=5)
    db.record_success("http://10.0.1.2:28444", best_height=7)
    db.record_failure("http://10.0.2.3:28444", penalty=50, reason="bad block")
    health = db.health_report()
    assert health["ok"] is True
    assert health["best_height"] == 7
    assert db.select_outbound_peers(target=2)
    assert db.prune_stale(older_than_seconds=10**9)["deleted"] >= 0


def test_sync_health_and_assignment():
    scheduler = HeaderSyncScheduler(retry_seconds=0)
    headers = [{"hash": "a" * 64, "height": 1}, {"hash": "b" * 64, "height": 2}]
    assert scheduler.plan_from_headers(FakeChain(), headers, "peer-a")["queued"] == 2
    assignments = scheduler.assign_ready_jobs(["peer-a", "peer-b"])
    assert len(assignments) == 2
    # Make a job look stale.
    scheduler.jobs["a" * 64].last_attempt_at = int(time.time()) - 999
    assert scheduler.health_report(stale_seconds=1)["stalled"]


def test_metrics_history_service_health():
    history = MetricsHistory()
    history.add(
        {"netcoin_block_height": 1, "netcoin_peer_count": 1, "netcoin_mempool_transactions": 0, "netcoin_timestamp": 1}
    )
    history.add(
        {
            "netcoin_block_height": 1,
            "netcoin_peer_count": 0,
            "netcoin_mempool_transactions": 0,
            "netcoin_timestamp": 4000,
        }
    )
    alerts = history.evaluate(stuck_seconds=10)
    health = service_health(history.latest(), alerts)
    assert health["status"] in {"degraded", "critical"}
    assert health["alert_count"] >= 1


def test_market_oracle_mm_and_reconciliation_enhancements():
    state = {}
    registry = OracleRegistry(state)
    registry.register_oracle("ap", "Associated Press", reputation=90)
    ev = registry.submit_evidence("m1", oracle_id="ap", title="Result", statement="YES won")
    assert ev["sha256"]
    assert registry.reputation_report()["active_count"] == 1
    assert registry.resolution_readiness("m1")["ready"] is True
    market = {
        "market_id": "m1",
        "status": "resolved",
        "winning_outcome_id": "YES",
        "unit_payout_sats": 100,
        "positions": {"maker": {"YES": 80, "NO": -20}},
        "wallets": {"maker": {"balance_sats": 1000, "reserved_sats": 0}},
    }
    assert inventory_risk(market, "maker", max_position=100)["risk_level"] in {"high", "medium"}
    assert rebalance_suggestions(market, "maker")["suggestion_count"] >= 1
    audit = settlement_audit_report(market)
    assert audit["ok"] is True
    assert any(c["name"] == "winning_outcome_selected" for c in audit["checks"])


def test_exchange_risk_limits_and_liabilities(tmp_path):
    ledger = ExchangeLedger(tmp_path / "exchange.sqlite")
    dep = ledger.record_deposit(
        txid="d" * 64, vout=0, address="addr", amount_sats=1000, height=1, required_confirmations=1, current_height=1
    )
    assert dep["state"] == "credited"
    ledger.request_withdrawal("wd1", address="addr2", amount_sats=600, fee_sats=10)
    risk = ledger.risk_limits_report(hot_wallet_balance_sats=500)
    assert risk["ok"] is False
    liabilities = ledger.outstanding_liabilities()
    assert liabilities["net_liability_sats"] == 390


def test_release_provenance_tools(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("netcoin")
    provenance = tmp_path / "artifact.provenance.json"
    subprocess.check_call(
        [sys.executable, "tools/generate_provenance.py", str(artifact), "--out", str(provenance)],
        cwd=Path(__file__).resolve().parents[1],
    )
    result = subprocess.check_output(
        [sys.executable, "tools/verify_provenance.py", str(artifact), str(provenance)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )
    assert json.loads(result)["ok"] is True
