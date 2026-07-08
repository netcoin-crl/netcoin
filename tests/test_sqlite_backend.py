"""SQLite storage backend (#21): persistence, restart, reorg, mempool, migration."""

import argparse
import json
from pathlib import Path

from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.storage import SqliteChainStore
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def test_sqlite_persists_chain_across_restart(tmp_path: Path):
    miner = Wallet.create()
    chain = Blockchain(tmp_path / "node", backend="sqlite")
    for _ in range(3):
        chain.mine_block(miner.address)
    tip = chain.tip_hash()
    assert (tmp_path / "node" / "netcoin.sqlite").exists()
    assert not (tmp_path / "node" / "chain.json").exists()  # no JSON when sqlite

    # Reopen from SQLite.
    reopened = Blockchain(tmp_path / "node", backend="sqlite")
    assert reopened.height() == 3
    assert reopened.tip_hash() == tip


def test_sqlite_mempool_persists(tmp_path: Path):
    miner = Wallet.create()
    receiver = Wallet.create()
    chain = Blockchain(tmp_path / "node", backend="sqlite")
    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)

    reopened = Blockchain(tmp_path / "node", backend="sqlite")
    assert tx.txid() in {e["txid"] for e in reopened.mempool_info()["entries"]}


def test_sqlite_handles_reorg(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = Blockchain(tmp_path / "a", backend="sqlite")
    for _ in range(2):
        a.mine_block(miner_a.address)

    # Heavier competing branch sharing block 1.
    b = Blockchain(tmp_path / "b")  # json is fine as a source
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
    # The reorged chain survives a restart from SQLite.
    reopened = Blockchain(tmp_path / "a", backend="sqlite")
    assert reopened.height() == 4
    assert reopened.tip_hash() == b.tip_hash()


def test_sqlite_store_unit(tmp_path: Path):
    miner = Wallet.create()
    src = Blockchain(tmp_path / "src")
    for _ in range(2):
        src.mine_block(miner.address)
    store = SqliteChainStore(tmp_path / "db.sqlite")
    assert store.has_chain() is False
    store.save_chain(src.chain)
    assert store.has_chain() is True
    loaded = store.load_chain()
    assert len(loaded) == len(src.chain)
    assert loaded[-1]["header"]["height"] == 2
    store.close()


def test_migrate_sqlite_cli(tmp_path: Path, capsys):
    miner = Wallet.create()
    data = tmp_path / "node"
    chain = Blockchain(data)  # json backend
    for _ in range(2):
        chain.mine_block(miner.address)

    cli.cmd_migrate_sqlite(argparse.Namespace(data=str(data)))
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["blocks"] == 3  # genesis + 2

    # Now open the same dir with the SQLite backend and confirm it matches.
    sqlite_chain = Blockchain(data, backend="sqlite")
    assert sqlite_chain.height() == 2
    assert sqlite_chain.tip_hash() == chain.tip_hash()
