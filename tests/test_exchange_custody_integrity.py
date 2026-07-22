from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def _deposit(store: AppStore, chain: Blockchain, customer_id: str, amount_sats: int, custody: Wallet):
    block = chain.mine_block(custody.segwit_address)
    txid = block.transactions[0].txid()
    return store.record_exchange_deposit(
        chain,
        {
            "customer_id": customer_id,
            "amount_sats": amount_sats,
            "tier": "hot",
            "custody_address": custody.segwit_address,
            "txid": txid,
        },
    )


def test_deposit_without_a_real_confirmed_txid_is_rejected(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    custody = Wallet.create()
    with pytest.raises(AppError, match="transaction not found"):
        store.record_exchange_deposit(
            chain,
            {"customer_id": "c1", "amount_sats": 1000, "custody_address": custody.segwit_address, "txid": "0" * 64},
        )


def test_deposit_txid_cannot_be_reused_to_inflate_balance(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    custody = Wallet.create()
    block = chain.mine_block(custody.segwit_address)
    txid = block.transactions[0].txid()
    payload = {"customer_id": "c1", "amount_sats": 1000, "custody_address": custody.segwit_address, "txid": txid}
    store.record_exchange_deposit(chain, payload)
    with pytest.raises(AppError, match="already used"):
        store.record_exchange_deposit(chain, dict(payload, customer_id="c2"))


def test_deposit_amount_must_actually_be_paid_by_the_transaction(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    custody = Wallet.create()
    block = chain.mine_block(custody.segwit_address)
    txid = block.transactions[0].txid()
    with pytest.raises(AppError, match="does not pay"):
        store.record_exchange_deposit(
            chain,
            {
                "customer_id": "c1",
                "amount_sats": 10**18,  # far more than the block subsidy
                "custody_address": custody.segwit_address,
                "txid": txid,
            },
        )


def test_withdrawal_cannot_exceed_customer_balance(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    custody = Wallet.create()
    _deposit(store, chain, "c1", 1000, custody)
    with pytest.raises(AppError, match="exceeds available balance"):
        store.request_exchange_withdrawal({"customer_id": "c1", "amount_sats": 2000, "to_address": custody.segwit_address})


def test_withdrawal_release_debits_customer_balance_and_hot_custody(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    custody = Wallet.create()
    _deposit(store, chain, "c1", 1000, custody)
    withdrawal = store.request_exchange_withdrawal({"customer_id": "c1", "amount_sats": 400, "to_address": custody.segwit_address})
    store.approve_exchange_withdrawal(withdrawal["withdrawal_id"], {"approver": "op-a"})
    result = store.approve_exchange_withdrawal(withdrawal["withdrawal_id"], {"approver": "op-b"})
    assert result["status"] == "released"
    data = store.load()
    assert data["exchange_customer_balances"]["c1"] == 600
    assert data["exchange_custody"]["hot"] == 600


def test_reserve_attestation_reflects_real_chain_verified_custody(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    custody = Wallet.create()
    _deposit(store, chain, "c1", 1000, custody)
    attestation = store.run_reserve_attestation(chain, {})
    assert attestation["chain_verified_reserve_sats"] > 0
