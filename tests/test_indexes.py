"""Persistent block/transaction indexes and chainstate integrity (#5, #6, #24)."""
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def test_block_and_tx_index_after_mining(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)

    tip = chain.tip()
    assert chain.get_block_by_hash(tip.hash()) is tip
    assert chain.get_block_by_hash("0" * 64) is None

    coinbase = tip.transactions[0]
    found = chain.get_transaction(coinbase.txid())
    assert found is not None
    tx, block = found
    assert tx.txid() == coinbase.txid()
    assert block.hash() == tip.hash()
    # Index covers every block (genesis + 3 mined).
    assert len(chain.block_index) == len(chain.chain)
    assert coinbase.txid() in chain.tx_index


def test_index_rebuilt_after_restart(tmp_path: Path):
    miner = Wallet.create()
    chain = Blockchain(tmp_path / "node")
    for _ in range(2):
        chain.mine_block(miner.address)
    tip_hash = chain.tip_hash()
    coinbase_txid = chain.tip().transactions[0].txid()

    # Fresh instance on the same data dir rebuilds the indexes.
    reloaded = Blockchain(tmp_path / "node")
    assert reloaded.get_block_by_hash(tip_hash) is not None
    assert reloaded.get_transaction(coinbase_txid) is not None
    assert len(reloaded.block_index) == len(reloaded.chain)


def test_index_follows_reorg(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = Blockchain(tmp_path / "a")
    for _ in range(2):
        a.mine_block(miner_a.address)
    disconnected_tip = a.tip_hash()

    # Heavier competing branch forking at height 1.
    b = Blockchain(tmp_path / "b")
    b.add_block(a.chain[1])
    for _ in range(3):
        b.mine_block(miner_b.address)

    for block in b.chain[2:]:
        try:
            a.add_block(block)
        except Exception:
            pass

    assert a.height() == 4
    assert a.tip_hash() == b.tip_hash()
    # The old tip (now off-chain) is no longer indexed; the new one is.
    assert a.get_block_by_hash(disconnected_tip) is None
    assert a.get_block_by_hash(b.tip_hash()) is not None
    assert set(a.block_index) == {blk.hash() for blk in a.chain}


def test_verify_integrity(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)
    report = chain.verify_integrity()
    assert report["ok"] is True
    assert report["index_consistent"] is True
    assert report["indexed_blocks"] == len(chain.chain)
    assert report["height"] == 3
