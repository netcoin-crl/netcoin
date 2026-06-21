"""Persistent/incremental UTXO set correctness (#22 foundation)."""
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def test_incremental_utxos_match_recompute_through_spends(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)

    # Spend, then mine the spend in.
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)

    # The incremental cache must equal a fresh full-scan recompute.
    assert set(chain._utxos) == set(chain._recompute_utxos_from_chain())
    report = chain.verify_integrity()
    assert report["utxo_consistent"] is True
    assert report["ok"] is True


def test_utxo_set_returns_independent_copy(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    before = len(chain._utxos)
    snapshot = chain.utxo_set()
    snapshot.clear()  # mutating the returned dict must not affect the chain
    assert len(chain._utxos) == before


def test_incremental_utxos_correct_after_reorg(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = Blockchain(tmp_path / "a")
    for _ in range(2):
        a.mine_block(miner_a.address)

    b = Blockchain(tmp_path / "b")
    b.add_block(a.chain[1])
    for _ in range(3):
        b.mine_block(miner_b.address)
    for block in b.chain[2:]:
        try:
            a.add_block(block)
        except Exception:
            pass

    assert a.tip_hash() == b.tip_hash()
    # After the reorg the cache was rebuilt and matches a recompute.
    assert set(a._utxos) == set(a._recompute_utxos_from_chain())
    assert a.verify_integrity()["utxo_consistent"] is True


def test_balances_use_persistent_cache(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    # Balance via the cache matches what the recompute would give.
    cached_total = sum(u.output.amount for u in chain._utxos.values() if u.output.address == miner.address)
    recomputed = chain._recompute_utxos_from_chain()
    recomputed_total = sum(u.output.amount for u in recomputed.values() if u.output.address == miner.address)
    assert cached_total == recomputed_total
    assert chain.balances_for_address(miner.address)["total"] == cached_total
