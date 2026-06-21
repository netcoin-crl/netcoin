from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.miner import solve_template
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
