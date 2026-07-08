"""Pruned mode (#22): prune old block bodies, reload from snapshot, keep running."""

from pathlib import Path

import pytest

from netcoin.chain import Blockchain, ChainError
from netcoin.wallet import Wallet


def test_prune_requires_sqlite(tmp_path: Path):
    chain = Blockchain(tmp_path / "json", backend="json")  # explicit legacy JSON backend
    with pytest.raises(ChainError, match="SQLite"):
        chain.prune(keep_depth=2)


def test_prune_then_reload_runs_in_pruned_mode(tmp_path: Path):
    miner = Wallet.create()
    data = tmp_path / "node"
    chain = Blockchain(data, backend="sqlite")
    for _ in range(8):
        chain.mine_block(miner.address)
    tip_before = chain.tip_hash()
    height_before = chain.height()
    utxo_count = len(chain._utxos)

    report = chain.prune(keep_depth=3)
    assert report["ok"] is True
    assert report["pruned_block_bodies"] > 0
    assert report["pruned_below_height"] == height_before - 3 + 1

    # Reload: the node comes up in pruned mode from the snapshot + kept tail.
    reloaded = Blockchain(data, backend="sqlite")
    assert reloaded.pruned is True
    assert reloaded.height() == height_before
    assert reloaded.tip_hash() == tip_before
    assert len(reloaded._utxos) == utxo_count
    # Old block bodies below the floor are gone.
    assert len(reloaded.chain) < height_before + 1
    integrity = reloaded.verify_integrity()
    assert integrity["pruned"] is True and integrity["ok"] is True


def test_pruned_node_can_keep_mining(tmp_path: Path):
    miner = Wallet.create()
    data = tmp_path / "node"
    chain = Blockchain(data, backend="sqlite")
    for _ in range(6):
        chain.mine_block(miner.address)
    chain.prune(keep_depth=3)

    reloaded = Blockchain(data, backend="sqlite")
    h = reloaded.height()
    new_block = reloaded.mine_block(miner.address)  # extend the pruned chain
    assert reloaded.height() == h + 1
    assert reloaded.tip_hash() == new_block.hash()

    # And the new tip survives another reload.
    again = Blockchain(data, backend="sqlite")
    assert again.height() == h + 1
    assert again.tip_hash() == new_block.hash()


def test_pruned_balances_still_correct(tmp_path: Path):
    miner = Wallet.create()
    data = tmp_path / "node"
    chain = Blockchain(data, backend="sqlite")
    for _ in range(5):
        chain.mine_block(miner.address)
    total_before = chain.balances_for_address(miner.address)["total"]
    chain.prune(keep_depth=2)

    reloaded = Blockchain(data, backend="sqlite")
    assert reloaded.balances_for_address(miner.address)["total"] == total_before
