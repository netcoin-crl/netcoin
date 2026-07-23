from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.storage import SqliteChainStore
from netcoin.wallet import Wallet


def test_mined_blocks_persist_incrementally_and_reload_correctly(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="sqlite")
    miner = Wallet.create()
    for _ in range(5):
        chain.mine_block(miner.address)
    hashes_before = [b.hash() for b in chain.chain]

    reloaded = Blockchain(tmp_path / "chain", backend="sqlite")
    hashes_after = [b.hash() for b in reloaded.chain]
    assert hashes_after == hashes_before
    assert reloaded.height() == chain.height()


def test_append_block_writes_only_the_new_position_not_a_full_rewrite(tmp_path: Path):
    store = SqliteChainStore(tmp_path / "chain.sqlite")
    chain = Blockchain(tmp_path / "chain-src", backend="sqlite")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)

    for position, block in enumerate(chain.chain):
        store.append_block(block, position)

    before_count = store.conn.execute("SELECT COUNT(*) FROM active_chain").fetchone()[0]
    assert before_count == len(chain.chain)

    extra = chain.chain[-1]
    store.append_block(extra, len(chain.chain))
    after_count = store.conn.execute("SELECT COUNT(*) FROM active_chain").fetchone()[0]
    assert after_count == before_count + 1

    loaded = store.load_chain()
    assert len(loaded) == len(chain.chain) + 1


def test_appended_position_uses_block_height_not_in_memory_list_length(tmp_path: Path):
    """A pruned node keeps only a tail of blocks in memory after reload, so
    appending a new tip must position it by the block's own height, not
    len(self.chain)."""
    miner = Wallet.create()
    data = tmp_path / "node"
    chain = Blockchain(data, backend="sqlite")
    for _ in range(6):
        chain.mine_block(miner.address)
    chain.prune(keep_depth=3)

    reloaded = Blockchain(data, backend="sqlite")
    assert len(reloaded.chain) < reloaded.height() + 1
    h = reloaded.height()
    new_block = reloaded.mine_block(miner.address)
    assert reloaded.height() == h + 1

    again = Blockchain(data, backend="sqlite")
    assert again.height() == h + 1
    assert again.tip_hash() == new_block.hash()
