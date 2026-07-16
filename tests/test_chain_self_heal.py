"""A corrupt SQLite chain store must self-heal on reload instead of crash-looping.

This pins the failure mode that took a public seed down for an hour: an OOM
kill caught the node mid-write, left a structurally broken block in
netcoin.sqlite, and every subsequent start crashed on 'block height does not
extend the previous block'. The node must instead recover automatically.
"""

import json
import sqlite3
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def _corrupt_active_chain(data_dir: Path) -> None:
    """Drop a middle block from the active-chain ordering so a reload sees a
    height gap — the exact 'does not extend the previous block' break."""
    conn = sqlite3.connect(data_dir / "netcoin.sqlite")
    conn.execute("DELETE FROM active_chain WHERE position = 2")
    conn.commit()
    conn.close()


def test_corrupt_sqlite_chain_self_heals_from_json_backup(tmp_path: Path):
    data = tmp_path / "chain"
    chain = Blockchain(data, backend="sqlite")
    miner = Wallet.create()
    for _ in range(4):
        chain.mine_block(miner.address)
    assert chain.height() == 4
    good_tip = chain.tip_hash()

    # A JSON snapshot exists (left by an earlier JSON-backend run, or a backup
    # cron) — recovery should rebuild from it and come back at full height.
    (data / "chain.json").write_text(json.dumps({"blocks": [b.to_dict() for b in chain.chain]}))
    chain.store.conn.close()
    _corrupt_active_chain(data)

    reloaded = Blockchain(data, backend="sqlite")
    assert reloaded.height() == 4, "node should self-heal to full height from the JSON backup"
    assert reloaded.tip_hash() == good_tip
    # And the rebuilt SQLite store must now be clean on a second reload.
    reloaded.store.conn.close()
    again = Blockchain(data, backend="sqlite")
    assert again.height() == 4


def test_corrupt_sqlite_chain_without_backup_falls_back_to_genesis(tmp_path: Path):
    data = tmp_path / "chain"
    chain = Blockchain(data, backend="sqlite")
    miner = Wallet.create()
    for _ in range(4):
        chain.mine_block(miner.address)
    assert chain.height() == 4
    chain.store.conn.close()

    # No JSON backup exists (a pure-SQLite node). With nothing to recover from,
    # the node must reset to genesis and stand ready to resync from peers — NOT
    # crash-loop. (In production the --peer seeds then refill the chain.)
    assert not (data / "chain.json").exists()
    _corrupt_active_chain(data)

    reloaded = Blockchain(data, backend="sqlite")
    assert reloaded.height() == 0, "node should reset to genesis and be ready to resync, not crash"
