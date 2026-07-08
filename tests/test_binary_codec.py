"""Lossless binary serialization codec (#15): round-trips tx/block preserving identity."""

from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.serialization import (
    block_from_binary,
    block_to_binary,
    tx_from_binary,
    tx_to_binary,
)
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def test_coinbase_tx_roundtrip(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    coinbase = chain.tip().transactions[0]

    decoded, offset = tx_from_binary(tx_to_binary(coinbase))
    assert offset == len(tx_to_binary(coinbase))
    assert decoded.to_dict() == coinbase.to_dict()
    assert decoded.txid() == coinbase.txid()
    assert decoded.is_coinbase


def test_signed_tx_roundtrip_preserves_txid(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))

    decoded, _ = tx_from_binary(tx_to_binary(tx))
    assert decoded.to_dict() == tx.to_dict()
    assert decoded.txid() == tx.txid()
    assert decoded.wtxid() == tx.wtxid()


def test_segwit_tx_roundtrip(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.segwit_address)  # fund the SegWit address
    # SegWit-style spend produces a witness stack.
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="segwit"
    )
    assert tx.has_witness
    decoded, _ = tx_from_binary(tx_to_binary(tx))
    assert decoded.to_dict() == tx.to_dict()
    assert decoded.wtxid() == tx.wtxid()


def test_block_roundtrip_preserves_hash(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    block = chain.tip()
    assert len(block.transactions) >= 2

    decoded = block_from_binary(block_to_binary(block))
    assert decoded.to_dict() == block.to_dict()
    assert decoded.hash() == block.hash()
    assert decoded.header.height == block.header.height
    assert [t.txid() for t in decoded.transactions] == [t.txid() for t in block.transactions]
