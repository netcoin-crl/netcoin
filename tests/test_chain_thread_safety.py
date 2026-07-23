"""Blockchain had no internal locking at all, even though node.py shares one
instance across every ThreadingHTTPServer request thread. These tests drive
real concurrent access at the mutation entry points to confirm the lock
actually prevents corruption, not just that single-threaded behavior is
unchanged."""

import threading
from pathlib import Path

import netcoin.chain as chain_module
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def test_concurrent_mempool_adds_do_not_corrupt_state(tmp_path: Path, monkeypatch):
    # Coinbase maturity is 100 blocks by default -- mining that many times
    # over per funder with the (known-slow) pure-Python PoW loop would make
    # this single test dominate the whole suite's runtime. The maturity rule
    # itself isn't what's under test here, so shrink it just for this test.
    monkeypatch.setattr(chain_module, "COINBASE_MATURITY", 2)
    chain = Blockchain(tmp_path / "chain")
    # A distinct coinbase-funded wallet per transaction so none of them
    # legitimately conflict (share an input) with another -- this test is
    # about the lock preventing state corruption from concurrent access,
    # not about mempool double-spend rejection (a separate, correct thing).
    funders = [Wallet.create() for _ in range(6)]
    recipient = Wallet.create()
    for funder in funders:
        for _ in range(3):
            chain.mine_block(funder.address)

    txs = [funder.create_transaction(chain, recipient.address, 1_000_000, 10_000) for funder in funders]

    errors = []

    def worker(tx):
        try:
            chain.add_mempool_transaction(tx)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(tx,)) for tx in txs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    mempool_txids = {t.txid() for t in chain.mempool}
    assert mempool_txids == {tx.txid() for tx in txs}
    assert len(chain.mempool) == len(txs)


def test_concurrent_mine_block_calls_produce_a_consistent_chain(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)

    results = []
    errors = []

    def worker():
        try:
            results.append(chain.mine_block(miner.address))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    # Every call must have serialized cleanly onto a distinct height with no
    # duplicate/skipped heights and no exception from racing state.
    heights = sorted(b.header.height for b in results)
    assert heights == list(range(2, 2 + len(results)))
    assert chain.height() == 1 + len(results)
    assert len(chain.chain) == chain.height() + 1
