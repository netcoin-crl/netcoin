"""Snapshot -> genesis-allocation migration: balances carry across a relaunch."""
from pathlib import Path

from netcoin.chain import Blockchain, create_genesis_block
from netcoin.migration import export_allocation, load_allocation, save_allocation
from netcoin.wallet import Wallet


def test_default_genesis_is_unchanged():
    # the live chain must be byte-identical when no allocation is given
    g = create_genesis_block()
    assert g.transactions[0].outputs == []
    assert create_genesis_block(None).hash() == g.hash()


def test_snapshot_preserves_every_balance(tmp_path: Path):
    old = Blockchain(tmp_path / "old")
    a, b = Wallet.create(), Wallet.create()
    for _ in range(60):
        old.mine_block(a.address)
    for _ in range(40):
        old.mine_block(b.address)

    allocation = export_allocation(old)
    assert allocation[a.address] == old.balances_for_address(a.address)["total"]
    assert allocation[b.address] == old.balances_for_address(b.address)["total"]

    new = Blockchain(tmp_path / "new", genesis_allocation=allocation)
    assert new.height() == 0
    for address, amount in allocation.items():
        assert new.balances_for_address(address)["total"] == amount


def test_allocation_file_round_trip(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    w = Wallet.create()
    for _ in range(5):
        chain.mine_block(w.address)
    allocation = export_allocation(chain)
    path = str(tmp_path / "alloc.json")
    save_allocation(allocation, path)
    assert load_allocation(path) == allocation


def test_allocated_chain_extends_normally(tmp_path: Path):
    old = Blockchain(tmp_path / "old")
    w = Wallet.create()
    for _ in range(10):
        old.mine_block(w.address)
    new = Blockchain(tmp_path / "new", genesis_allocation=export_allocation(old))
    # the new chain mines on top of the allocated genesis without issue
    miner = Wallet.create()
    new.mine_block(miner.address)
    assert new.height() == 1
