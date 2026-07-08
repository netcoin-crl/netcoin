from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from netcoin.apps import AppStore
from netcoin.chain import Blockchain
from netcoin.exchange import ExchangeLedger
from netcoin.indexer import ChainIndexer
from netcoin.metrics import collect_metrics, evaluate_alerts, prometheus_text
from netcoin.peerdb import PeerDatabase
from netcoin.recovery import encrypted_backup_validate, gap_limit_scan_preview, seed_backup_check
from netcoin.sync import HeaderSyncScheduler
from netcoin.tx import amount_to_sats
from netcoin.tx_simulator import simulate_transaction
from netcoin.wallet import Wallet


def test_batch1_indexer_wallet_simulator_and_recovery_center(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner, phrase = Wallet.create_with_mnemonic()
    receiver = Wallet.create()
    for _ in range(106):
        chain.mine_block(miner.address)

    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    preview = simulate_transaction(
        chain,
        tx,
        wallet_addresses=[miner.address],
        frozen_outpoints=[tx.inputs[0].outpoint()],
        recent_addresses=[receiver.address[:-3] + "xxx"],
    )
    assert preview["fee_sats"] == amount_to_sats("0.01")
    assert any(w["code"] == "frozen_coin" for w in preview["warnings"])
    assert preview["recipient_outputs"][0]["address"] == receiver.address

    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    indexer = ChainIndexer(tmp_path / "explorer.sqlite")
    result = indexer.rebuild(chain)
    assert result["indexed_blocks"] == chain.height() + 1
    history = indexer.address_history(receiver.address)
    assert history["balance_sats"] >= amount_to_sats("1")
    graph = indexer.tx_graph(tx.txid())
    assert graph["found"] is True
    assert graph["outputs"]

    seed = seed_backup_check(phrase, expected_address=miner.address)
    assert seed["valid"] is True
    assert seed["matched_index"] == 0
    scan = gap_limit_scan_preview(chain, phrase, gap_limit=3, max_index=8)
    assert scan["used_count"] >= 1
    wallet_file = tmp_path / "wallet.json"
    miner.save(wallet_file, passphrase="pw")
    assert encrypted_backup_validate(wallet_file, "pw")["ok"] is True


def test_batch2_peerdb_sync_and_metrics(tmp_path: Path):
    db = PeerDatabase(tmp_path / "peers.sqlite")
    db.upsert_peer("http://10.0.0.1:28444", anchor=True, best_height=5)
    db.upsert_peer("http://10.0.0.2:28444")
    db.record_success("http://10.0.0.1:28444", latency_ms=12, best_height=6)
    db.record_failure("http://10.0.0.2:28444", penalty=25, ban_threshold=-20)
    candidates = db.candidates(include_banned=False)
    assert candidates[0]["anchor"] == 1
    assert all(not item["banned"] for item in candidates)
    assert db.export_node_map()["peer_count"] >= 2

    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    headers = chain.header_list(1, 5)
    follower = Blockchain(tmp_path / "follower")
    scheduler = HeaderSyncScheduler()
    planned = scheduler.plan_from_headers(follower, headers, "peer-a")
    assert planned["queued"] == 1
    job = scheduler.next_jobs()[0]
    scheduler.mark_attempt(job.block_hash)
    scheduler.mark_failed(job.block_hash, "timeout")
    assert scheduler.progress()["status_counts"]["retry"] == 1

    metrics = collect_metrics(chain)
    text = prometheus_text(metrics)
    assert "netcoin_block_height" in text
    alerts = evaluate_alerts(
        metrics | {"netcoin_peer_count": 0},
        previous_height=chain.height(),
        previous_timestamp=int(metrics["netcoin_timestamp"]) - 3600,
    )
    assert {a["alert"] for a in alerts} >= {"NetCoinNoPeers", "NetCoinStuckChain"}


def test_batch3_market_oracles_maker_and_reconciliation(tmp_path: Path):
    store = AppStore(tmp_path / "app")
    market = store.create_prediction_market(
        {
            "question": "Will Batch 3 pass?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "sandbox_short_mode": True,
        }
    )
    market_id = market["market_id"]
    oracle = store.register_market_oracle({"oracle_id": "manual", "name": "Manual resolver"})
    assert oracle["active"] is True
    evidence = store.submit_market_evidence(
        market_id, {"oracle_id": "manual", "title": "Test evidence", "statement": "Unit test says yes"}
    )
    assert evidence["sha256"]
    dispute = store.dispute_market_evidence(market_id, {"commenter": "auditor", "comment": "Looks valid"})
    assert dispute["market_id"] == market_id
    dossier = store.market_oracle_dossier(market_id)
    assert dossier["evidence_count"] == 1
    plan = store.market_maker_quote_plan(market_id, {"trader": "demo:mm", "quantity": 3, "spread_bps": 100})
    assert plan["quote_count"] == 2
    assert len(plan["orders"]) == 4
    resolved = store.resolve_prediction_market(
        market_id, {"winning_outcome_id": market["outcomes"][0]["outcome_id"], "operator_approved": True}
    )
    assert resolved["status"] == "resolved"
    recon = store.market_settlement_reconciliation(market_id)
    assert recon["ok"] is True


def test_batch4_exchange_sdk_openapi_and_release_signature(tmp_path: Path):
    ledger = ExchangeLedger(tmp_path / "exchange.sqlite")
    dep = ledger.record_deposit(
        txid="a" * 64,
        vout=0,
        address="net-demo",
        amount_sats=1234,
        height=5,
        current_height=5,
        required_confirmations=2,
    )
    assert dep["state"] == "confirming"
    ledger.update_deposit_confirmations(6)
    assert ledger.get_deposit(dep["deposit_id"])["state"] == "credited"
    wd = ledger.request_withdrawal("wd1", address="net-demo", amount_sats=1000, requested_by="alice")
    assert wd["state"] == "requested"
    assert ledger.transition_withdrawal("wd1", "approved", operator="ops")["approved_by"] == "ops"
    assert ledger.transition_withdrawal("wd1", "signed", operator="signer", raw_tx="raw")["state"] == "signed"
    assert ledger.transition_withdrawal("wd1", "broadcast", txid="b" * 64)["txid"] == "b" * 64

    sdk_path = Path("sdk/netcoin-python")
    sys.path.insert(0, str(sdk_path))
    try:
        import netcoin_sdk

        envelope = netcoin_sdk.build_signed_envelope(
            "net1qexample", "POST", "/api/tokens", {"symbol": "B"}, lambda msg: "sig:" + msg[:8]
        )
        assert envelope["body_hash"] == netcoin_sdk.canonical_body_hash({"symbol": "B"})
        assert envelope["signature"].startswith("sig:")
    finally:
        sys.path.remove(str(sdk_path))

    assert subprocess.run([sys.executable, "tools/check_openapi_contract.py"], cwd=Path.cwd()).returncode == 0
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("release")
    wallet = Wallet.create()
    wallet_file = tmp_path / "release-wallet.json"
    wallet.save(wallet_file)
    sig_path = tmp_path / "artifact.sig.json"
    subprocess.check_call(
        [sys.executable, "tools/sign_release.py", str(artifact), "--wallet", str(wallet_file), "--out", str(sig_path)],
        cwd=Path.cwd(),
    )
    subprocess.check_call([sys.executable, "tools/verify_signature.py", str(artifact), str(sig_path)], cwd=Path.cwd())
