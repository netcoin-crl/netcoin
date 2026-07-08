import json
import time
from pathlib import Path

import pytest

from netcoin.exchange import ExchangeLedger
from netcoin.faucet_abuse import daily_spend_report, issue_challenge, reputation_score, solve_pow, verify_pow
from netcoin.psbt import PartiallySignedTransaction
from netcoin.signer import HardwareSigner, SimulatedHardwareTransport, signer_status
from netcoin.sync import HeaderSyncError, HeaderSyncScheduler, PeerSyncCoordinator, validate_headers_linked
from netcoin.tx import SpendableOutput, TxOutput
from netcoin.wallet import Wallet
from netcoin.peerdb import PeerDatabase


def _sample_psbt(wallet: Wallet) -> PartiallySignedTransaction:
    prevout = SpendableOutput(
        txid="11" * 32,
        vout=0,
        output=TxOutput(amount=100_000, address=wallet.address),
        height=1,
    )
    return PartiallySignedTransaction.create([prevout], [TxOutput(amount=90_000, address=wallet.address)])


def test_hardware_signer_transport_signs_psbt_in_dev_mode():
    wallet = Wallet.create()
    psbt = _sample_psbt(wallet)
    signer = HardwareSigner("dev-device", transport=SimulatedHardwareTransport(wallet), require_real_device=False)
    assert signer.can_sign() is True
    signed = signer.sign_psbt(psbt)
    assert signed.is_fully_signed()
    status = signer_status(signer)
    assert status["transport"] == "simulated-hardware-transport"
    assert status["experimental_stub"] is False


def test_header_sync_rejects_bad_links_and_penalizes_peer(tmp_path: Path):
    peerdb = PeerDatabase(tmp_path / "peers.sqlite")
    peerdb.upsert_peer("127.0.0.1:18444")
    coordinator = PeerSyncCoordinator(peerdb)
    good = [
        {"height": 1, "previous_hash": "00" * 32, "hash": "aa" * 32, "work": 2},
        {"height": 2, "previous_hash": "aa" * 32, "hash": "bb" * 32, "work": 3},
    ]
    result = coordinator.record_headers("127.0.0.1:18444", good, local_tip_hash="00" * 32, local_height=0)
    assert result["queued"] == 2
    plan = coordinator.assignment_plan(target=2)
    assert len(plan["assignments"]) == 2
    bad = [{"height": 3, "previous_hash": "not-linked", "hash": "cc" * 32}]
    with pytest.raises(HeaderSyncError):
        validate_headers_linked(bad, expected_previous_hash="bb" * 32, expected_start_height=3)
    with pytest.raises(Exception):
        coordinator.record_headers("127.0.0.1:18444", bad, local_tip_hash="bb" * 32, local_height=2)
    assert peerdb.get_peer("127.0.0.1:18444")["failures"] >= 1


def test_exchange_hot_cold_custody_approval_policy(tmp_path: Path):
    ledger = ExchangeLedger(tmp_path / "exchange.sqlite")
    ledger.configure_custody_account(
        "hot-1",
        kind="hot",
        address="net1hot",
        balance_sats=5_000_000,
        single_limit_sats=4_000_000,
        min_approvals=2,
    )
    ledger.configure_custody_account("cold-1", kind="cold", address="net1cold", balance_sats=100_000_000)
    ledger.request_withdrawal("wd-1", address="net1recipient", amount_sats=3_000_000, fee_sats=1_000)
    policy = ledger.withdrawal_policy("wd-1")
    assert policy["ready_to_sign"] is False
    ledger.approve_withdrawal("wd-1", operator="alice")
    policy = ledger.approve_withdrawal("wd-1", operator="bob")
    assert policy["ready_to_sign"] is True
    batch = ledger.prepare_hot_withdrawal_batch()
    assert batch["ready_count"] == 1
    transfer = ledger.record_cold_to_hot_transfer(
        cold_account_id="cold-1", hot_account_id="hot-1", amount_sats=2_000_000
    )
    assert transfer["ok"] is True
    assert ledger.custody_status()["hot_wallet_coverage_ok"] is True


def test_faucet_pow_reputation_and_daily_cap():
    challenge = issue_challenge("203.0.113.9", secret="test-secret", difficulty=3, now=1000)
    nonce = solve_pow(challenge.challenge, difficulty=3, max_nonce=100_000)
    assert verify_pow(challenge.challenge, nonce, difficulty=3)
    state = {
        "requests": [{"ip": "1.1.1.1", "address": "addr", "amount": "5", "timestamp": int(time.time())}],
        "abuse": [],
    }
    spend = daily_spend_report(state, cap_sats=600_000_000, amount_sats=200_000_000)
    assert spend["would_exceed"] is True
    risky = {
        "requests": [],
        "queue": [],
        "abuse": [{"ip": "9.9.9.9", "timestamp": int(time.time()), "reason": "pow-failed"} for _ in range(7)],
    }
    assert reputation_score(risky, ip="9.9.9.9")["risk"] in {"challenge", "block"}
