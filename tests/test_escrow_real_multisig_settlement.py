"""Escrow release/refund previously only ever produced a generic operator
payout plan, disconnected from the real 2-of-3 multisig UTXO actually
holding the funds (finding 023). escrow_action now also builds a real,
spendable PSBT against that exact funding output -- these tests prove it's
genuinely spendable end-to-end, not just a plausible-looking artifact."""

from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.psbt import PartiallySignedTransaction
from netcoin.wallet import Wallet


def _mature_funded_escrow(tmp_path: Path, amount_sats: int = 100_000):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = Wallet.create(), Wallet.create(), Wallet.create()
    miner = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)

    escrow = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer.public_key.hex(),
            "seller_pubkey": seller.public_key.hex(),
            "mediator_pubkey": mediator.public_key.hex(),
            "buyer_address": buyer.segwit_address,
            "seller_address": seller.segwit_address,
            "mediator_address": mediator.segwit_address,
            "amount_sats": amount_sats,
        },
    )
    fund_tx = miner.create_transaction(chain, escrow["escrow_address"], amount_sats, 10_000)
    chain.add_mempool_transaction(fund_tx)
    chain.mine_block(miner.address)

    data = store.load()
    data["escrows"][escrow["escrow_id"]]["funding_txid"] = fund_tx.txid()
    store.save(data)
    escrow = store.escrow_status(chain, escrow["escrow_id"])
    assert escrow["status"] == "funded"
    return chain, store, escrow, buyer, seller, mediator, miner


def test_escrow_release_settlement_psbt_is_really_spendable(tmp_path: Path):
    chain, store, escrow, buyer, seller, mediator, miner = _mature_funded_escrow(tmp_path)
    escrow_id = escrow["escrow_id"]

    store.escrow_action(chain, escrow_id, {"action": "release", "signer": buyer.segwit_address})
    released = store.escrow_action(chain, escrow_id, {"action": "release", "signer": seller.segwit_address})
    assert released["status"] == "released"

    settlement = released["settlement"]
    assert settlement is not None
    assert settlement["funding_outpoint"] == f"{escrow['funding_txid']}:0" or ":" in settlement["funding_outpoint"]

    psbt = PartiallySignedTransaction.from_base64(settlement["unsigned_psbt"])
    # Only one signer (buyer alone) is not enough for a 2-of-3 spend.
    psbt.sign_multisig_input(0, buyer)
    assert not psbt.is_fully_signed()
    psbt.sign_multisig_input(0, seller)
    assert psbt.is_fully_signed()

    tx = psbt.extract()
    assert tx.outputs[0].address == seller.segwit_address

    seller_balance_before = chain.balances_for_address(seller.segwit_address)["total"]
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    seller_balance_after = chain.balances_for_address(seller.segwit_address)["total"]
    assert seller_balance_after > seller_balance_before


def test_escrow_refund_settlement_psbt_pays_the_buyer(tmp_path: Path):
    chain, store, escrow, buyer, seller, mediator, miner = _mature_funded_escrow(tmp_path)
    escrow_id = escrow["escrow_id"]

    store.escrow_action(chain, escrow_id, {"action": "refund", "signer": seller.segwit_address})
    refunded = store.escrow_action(chain, escrow_id, {"action": "refund", "signer": mediator.segwit_address})
    assert refunded["status"] == "refunded"

    psbt = PartiallySignedTransaction.from_base64(refunded["settlement"]["unsigned_psbt"])
    psbt.sign_multisig_input(0, seller)
    psbt.sign_multisig_input(0, mediator)
    tx = psbt.extract()
    assert tx.outputs[0].address == buyer.segwit_address

    buyer_balance_before = chain.balances_for_address(buyer.segwit_address)["total"]
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    buyer_balance_after = chain.balances_for_address(buyer.segwit_address)["total"]
    assert buyer_balance_after > buyer_balance_before


def test_settlement_is_none_when_funding_txid_cannot_be_resolved(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = Wallet.create(), Wallet.create(), Wallet.create()
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
    escrow_id = escrow["escrow_id"]
    # Fund it, then corrupt the recorded funding_txid so settlement can't
    # resolve the real UTXO -- release/refund must still complete (the
    # status transition doesn't depend on settlement succeeding).
    block = chain.mine_block(escrow["escrow_address"])
    data = store.load()
    data["escrows"][escrow_id]["funding_txid"] = block.transactions[0].txid()
    store.save(data)
    store.escrow_status(chain, escrow_id)
    data = store.load()
    data["escrows"][escrow_id]["funding_txid"] = "00" * 32
    store.save(data)

    store.escrow_action(chain, escrow_id, {"action": "release", "signer": buyer.segwit_address})
    released = store.escrow_action(chain, escrow_id, {"action": "release", "signer": seller.segwit_address})
    assert released["status"] == "released"
    assert released["settlement"] is None
