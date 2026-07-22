from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def _wallets():
    return Wallet.create(), Wallet.create(), Wallet.create()


def _fund(store: AppStore, chain: Blockchain, escrow: dict) -> dict:
    block = chain.mine_block(escrow["escrow_address"])
    data = store.load()
    data["escrows"][escrow["escrow_id"]]["funding_txid"] = block.transactions[0].txid()
    store.save(data)
    return store.escrow_status(chain, escrow["escrow_id"])


def test_create_escrow_rejects_reused_pubkey_as_two_roles(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, _ = _wallets()
    with pytest.raises(AppError, match="three distinct pubkeys"):
        store.create_escrow(
            chain,
            {
                "buyer_pubkey": buyer.public_key.hex(),
                "seller_pubkey": seller.public_key.hex(),
                "mediator_pubkey": buyer.public_key.hex(),
                "amount_sats": 1000,
            },
        )


def test_escrow_funding_txid_must_actually_pay_the_escrow_address(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = _wallets()
    unrelated = chain.mine_block(Wallet.create().segwit_address)
    with pytest.raises(AppError, match="does not pay"):
        store.create_escrow(
            chain,
            {
                "buyer_pubkey": buyer.public_key.hex(),
                "seller_pubkey": seller.public_key.hex(),
                "mediator_pubkey": mediator.public_key.hex(),
                "amount_sats": 1000,
                "funding_txid": unrelated.transactions[0].txid(),
            },
        )


def test_same_funding_txid_cannot_fund_two_different_escrows(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = _wallets()
    escrow_a = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer.public_key.hex(),
            "seller_pubkey": seller.public_key.hex(),
            "mediator_pubkey": mediator.public_key.hex(),
            "amount_sats": 1000,
        },
    )
    block = chain.mine_block(escrow_a["escrow_address"])
    txid = block.transactions[0].txid()
    data = store.load()
    data["escrows"][escrow_a["escrow_id"]]["funding_txid"] = txid
    store.save(data)
    funded_a = store.escrow_status(chain, escrow_a["escrow_id"])
    assert funded_a["status"] == "funded"

    buyer2, seller2, mediator2 = _wallets()
    escrow_b = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer2.public_key.hex(),
            "seller_pubkey": seller2.public_key.hex(),
            "mediator_pubkey": mediator2.public_key.hex(),
            "amount_sats": 1000,
        },
    )
    data = store.load()
    data["escrows"][escrow_b["escrow_id"]]["funding_txid"] = txid
    store.save(data)
    result_b = store.escrow_status(chain, escrow_b["escrow_id"])
    assert result_b["status"] == "funding_ready"


def test_release_cannot_fire_before_escrow_is_funded(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = _wallets()
    escrow = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer.public_key.hex(),
            "seller_pubkey": seller.public_key.hex(),
            "mediator_pubkey": mediator.public_key.hex(),
            "buyer_address": buyer.segwit_address,
            "seller_address": seller.segwit_address,
            "mediator_address": mediator.segwit_address,
            "amount_sats": 1000,
        },
    )
    with pytest.raises(AppError, match="must be funded"):
        store.escrow_action(escrow["escrow_id"], {"action": "release", "signer": buyer.segwit_address})


def test_terminal_state_rejects_further_actions(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = _wallets()
    escrow = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer.public_key.hex(),
            "seller_pubkey": seller.public_key.hex(),
            "mediator_pubkey": mediator.public_key.hex(),
            "buyer_address": buyer.segwit_address,
            "seller_address": seller.segwit_address,
            "mediator_address": mediator.segwit_address,
            "amount_sats": 1000,
        },
    )
    escrow = _fund(store, chain, escrow)
    assert escrow["status"] == "funded"
    store.escrow_action(escrow["escrow_id"], {"action": "release", "signer": buyer.segwit_address})
    released = store.escrow_action(escrow["escrow_id"], {"action": "release", "signer": seller.segwit_address})
    assert released["status"] == "released"
    with pytest.raises(AppError, match="already released"):
        store.escrow_action(escrow["escrow_id"], {"action": "refund", "signer": buyer.segwit_address})


def test_contracts_record_reflects_current_status_after_action(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = _wallets()
    escrow = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer.public_key.hex(),
            "seller_pubkey": seller.public_key.hex(),
            "mediator_pubkey": mediator.public_key.hex(),
            "buyer_address": buyer.segwit_address,
            "seller_address": seller.segwit_address,
            "mediator_address": mediator.segwit_address,
            "amount_sats": 1000,
        },
    )
    escrow = _fund(store, chain, escrow)
    store.escrow_action(escrow["escrow_id"], {"action": "release", "signer": buyer.segwit_address})
    store.escrow_action(escrow["escrow_id"], {"action": "release", "signer": seller.segwit_address})
    data = store.load()
    assert data["contracts"][escrow["escrow_id"]]["status"] == "released"
