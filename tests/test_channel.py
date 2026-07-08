"""Lightning-style payment channels: 2-of-2 funding, off-chain balance updates,
and a cooperative close that settles the final balances on-chain."""

from pathlib import Path

import pytest

from netcoin.chain import Blockchain
from netcoin.channel import PaymentChannel
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def test_open_and_offchain_payments():
    ch = PaymentChannel.open("aa", "bb", 1000)
    assert ch.balance_a == 1000 and ch.balance_b == 0 and ch.version == 0
    ch.pay("a", 400)
    ch.pay("b", 100)
    assert ch.balance_a == 700 and ch.balance_b == 300 and ch.version == 2
    with pytest.raises(ValueError):
        ch.pay("b", 10_000)  # can't overspend a side


def test_funding_address_is_2of2_multisig():
    a, b = Wallet.create(), Wallet.create()
    ch = PaymentChannel.open(a.public_key_hex, b.public_key_hex, 5000)
    # deterministic from the two pubkeys; both orderings of opener see the same script
    assert ch.address == PaymentChannel.open(a.public_key_hex, b.public_key_hex, 1).address
    assert "OP_CHECKMULTISIG" in ch.redeem_script


def test_full_channel_lifecycle_settles_on_chain(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    A, B = Wallet.create(), Wallet.create()
    for _ in range(103):
        chain.mine_block(A.address)

    cap = amount_to_sats("10")
    ch = PaymentChannel.open(A.public_key_hex, B.public_key_hex, cap)

    # open: A funds the 2-of-2 address
    ftx = A.create_transaction(chain, ch.address, cap, amount_to_sats("0.01"), from_type="legacy")
    chain.add_mempool_transaction(ftx)
    chain.mine_block(A.address)
    futxo = chain.utxos_for_address(ch.address)[0]
    ch.set_funding(futxo.txid, futxo.vout, futxo.output.amount)

    # off-chain payments
    ch.pay("a", amount_to_sats("3"))
    ch.pay("a", amount_to_sats("1.5"))
    ch.pay("b", amount_to_sats("0.5"))  # A=6, B=4

    # cooperative close
    close = ch.settlement_tx(A.address, B.address, fee=amount_to_sats("0.01"))
    ch.cosign(close, A.private_key, B.private_key)
    assert close.verify_input(0, ch.funding_prevout()) is True
    chain.add_mempool_transaction(close)
    chain.mine_block(A.address)

    assert chain.balances_for_address(B.address)["total"] == ch.balance_b  # B got 4 NET


def test_close_requires_both_signatures(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    A, B = Wallet.create(), Wallet.create()
    for _ in range(103):
        chain.mine_block(A.address)
    cap = amount_to_sats("5")
    ch = PaymentChannel.open(A.public_key_hex, B.public_key_hex, cap)
    ftx = A.create_transaction(chain, ch.address, cap, amount_to_sats("0.01"), from_type="legacy")
    chain.add_mempool_transaction(ftx)
    chain.mine_block(A.address)
    futxo = chain.utxos_for_address(ch.address)[0]
    ch.set_funding(futxo.txid, futxo.vout, futxo.output.amount)
    ch.pay("a", amount_to_sats("2"))

    close = ch.settlement_tx(A.address, B.address, fee=amount_to_sats("0.01"))
    # only A signs (B replaced by a stranger) -> 2-of-2 fails
    stranger = Wallet.create()
    ch.cosign(close, A.private_key, stranger.private_key)
    assert close.verify_input(0, ch.funding_prevout()) is False
