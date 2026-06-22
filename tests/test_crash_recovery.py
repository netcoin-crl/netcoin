"""Crash-safe persistence and reindex (#14): atomic writes, backup recovery,
corrupt-file tolerance, and rebuilding chainstate from block data."""
from pathlib import Path

import pytest

from netcoin.chain import Blockchain, ChainError
from netcoin.wallet import Wallet


def _funded_chain(tmp_path: Path, blocks: int = 3) -> Blockchain:
    chain = Blockchain(tmp_path / "data")
    miner = Wallet.create()
    for _ in range(blocks):
        chain.mine_block(miner.address)
    return chain


# --- atomic write hygiene ---

def test_save_leaves_no_temp_and_writes_backup(tmp_path: Path):
    chain = _funded_chain(tmp_path)
    d = chain.chain_path.parent
    # The atomic write must not leave a stray .tmp behind.
    assert not (d / (chain.chain_path.name + ".tmp")).exists()
    # A backup mirroring the live file must exist.
    bak = d / (chain.chain_path.name + ".bak")
    assert bak.exists()
    assert bak.read_text() == chain.chain_path.read_text()


# --- recovery from a corrupt live file ---

def test_recovers_from_backup_without_losing_blocks(tmp_path: Path):
    chain = _funded_chain(tmp_path, blocks=4)
    height = chain.height()
    # Simulate on-disk corruption of the live chain file.
    chain.chain_path.write_text("{ not valid json at all")
    reopened = Blockchain(tmp_path / "data")
    # Recovered to the full height from the up-to-date backup (no block lost).
    assert reopened.height() == height
    # And the canonical file is healed back to valid JSON on load.
    assert reopened.chain_path.read_text() == (
        chain.chain_path.parent / (chain.chain_path.name + ".bak")
    ).read_text()


def test_recovers_from_leftover_tmp_when_live_missing(tmp_path: Path):
    chain = _funded_chain(tmp_path, blocks=2)
    good = chain.chain_path.read_text()
    # Simulate a crash mid-write: only a .tmp survived, live + backup are gone.
    (chain.chain_path.parent / (chain.chain_path.name + ".tmp")).write_text(good)
    chain.chain_path.unlink()
    (chain.chain_path.parent / (chain.chain_path.name + ".bak")).unlink()
    reopened = Blockchain(tmp_path / "data")
    assert reopened.height() == chain.height()


def test_unrecoverable_chain_raises_clearly(tmp_path: Path):
    chain = _funded_chain(tmp_path, blocks=2)
    d = chain.chain_path.parent
    # Corrupt every copy: live, backup, and any temp.
    for suffix in ("", ".bak", ".tmp"):
        p = d / (chain.chain_path.name + suffix)
        p.write_text("garbage")
    with pytest.raises(ChainError, match="corrupt or unreadable"):
        Blockchain(tmp_path / "data")


# --- mempool is non-critical: corruption must not block startup ---

def test_corrupt_mempool_does_not_prevent_startup(tmp_path: Path):
    chain = _funded_chain(tmp_path, blocks=2)
    chain.mempool_path.write_text("}{ broken")
    reopened = Blockchain(tmp_path / "data")
    assert reopened.height() == chain.height()
    assert reopened.mempool == []


# --- reindex rebuilds chainstate ---

def test_reindex_rebuilds_consistent_chainstate(tmp_path: Path):
    chain = _funded_chain(tmp_path, blocks=3)
    chain.reindex()
    report = chain.verify_integrity()
    assert report["ok"] is True
    assert report["index_consistent"] and report["utxo_consistent"]
    assert report["height"] == chain.height()
