from pathlib import Path

from netcoin.block import validate_witness_commitment
from netcoin.chain import Blockchain
from netcoin.miner import solve_template
from netcoin.params import MIN_DIFFICULTY_GAP_SECONDS, POW_LIMIT_BITS
from netcoin.wallet import Wallet


def test_solve_template_and_submit_block(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()

    template = chain.get_block_template(miner_address=miner.address)
    assert template["height"] == 1
    block = solve_template(template, miner.address)

    block_hash = chain.add_block(block)
    assert block_hash == block.hash()
    assert chain.add_block(block) == block.hash()
    assert chain.height() == 1
    assert chain.tip_hash() == block.hash()


def test_block_template_includes_mempool_transaction_payload(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()

    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(chain, receiver.address, 100_000_000, 100_000)
    chain.add_mempool_transaction(tx)

    template = chain.get_block_template(miner_address=miner.address)
    assert template["transactions"][0]["txid"] == tx.txid()
    assert template["transactions"][0]["tx"]["outputs"][0]["address"] == receiver.address

    block = solve_template(template, miner.address)
    assert any(item.txid() == tx.txid() for item in block.transactions)
    chain.add_block(block)
    assert chain.height() == 102


def test_solve_template_adds_witness_commitment_for_witness_transactions(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()

    for _ in range(101):
        chain.mine_block(miner.segwit_address)
    tx = miner.create_transaction(
        chain,
        receiver.segwit_address,
        amount=100_000_000,
        fee=1_000,
        from_type="p2wpkh",
    )
    assert tx.has_witness
    chain.add_mempool_transaction(tx)

    template = chain.get_block_template(miner_address=miner.segwit_address)
    block = solve_template(template, miner.segwit_address)

    assert any(item.txid() == tx.txid() for item in block.transactions)
    assert validate_witness_commitment(block) is True
    chain.add_block(block)
    assert chain.height() == 102


def test_block_template_uses_testnet_lone_miner_floor_when_tip_is_old(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)

    chain.tip().header.timestamp -= MIN_DIFFICULTY_GAP_SECONDS + 1
    template = chain.get_block_template(miner_address=miner.address)

    assert template["bits"] == POW_LIMIT_BITS
    block = solve_template(template, miner.address)
    chain.add_block(block)
    assert chain.height() == 2
