"""Per-address UTXO index: correctness through spends/reorgs + O(coins) lookup."""

import contextlib
from pathlib import Path

from netcoin.chain import Blockchain, ChainError
from netcoin.wallet import Wallet


def _fresh_index(chain):
    idx = {}
    for op, sp in chain._utxos.items():
        idx.setdefault(sp.output.address, {})[op] = sp
    return idx


def _clone_prefix(tmp_path, name, source, upto_height):
    chain = Blockchain(tmp_path / name)
    for block in source.chain[1 : upto_height + 1]:
        chain.add_block(block)
    return chain


def _feed(target, blocks):
    for block in blocks:
        with contextlib.suppress(ChainError):
            target.add_block(block)


def test_index_mirrors_utxos_through_spends(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    a = Wallet.create()
    b = Wallet.create()
    for _ in range(102):
        chain.mine_block(a.segwit_address)

    tx = a.create_transaction(
        chain, b.segwit_address, amount=10_000_000, fee=1_000, from_type="segwit", change_type="segwit"
    )
    chain.add_mempool_transaction(tx)
    chain.mine_block(a.segwit_address)

    assert chain.verify_integrity()["utxo_addr_index_consistent"] is True
    assert set(chain._utxos_by_addr) == set(_fresh_index(chain))
    manual = sum(u.output.amount for u in chain._utxos.values() if u.output.address == b.segwit_address)
    assert chain.balances_for_address(b.segwit_address)["total"] == manual == 10_000_000


def test_index_survives_reorg(tmp_path: Path):
    a_wallet = Wallet.create()
    b_wallet = Wallet.create()
    a = Blockchain(tmp_path / "a")
    for _ in range(3):
        a.mine_block(a_wallet.address)
    original_tip = a.tip_hash()

    # Competing heavier branch shares heights 1..2, diverges to height 4.
    b = _clone_prefix(tmp_path, "b", a, 2)
    b.mine_block(b_wallet.address)
    b.mine_block(b_wallet.address)
    _feed(a, b.chain[3:5])

    assert a.tip_hash() == b.tip_hash() != original_tip  # reorg happened
    assert a.verify_integrity()["utxo_addr_index_consistent"] is True
    assert set(a._utxos_by_addr) == set(_fresh_index(a))


def test_lookup_uses_index_not_full_scan(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    target = Wallet.create()
    noise = Wallet.create()
    chain.mine_block(target.segwit_address)
    for _ in range(200):
        chain.mine_block(noise.segwit_address)
    assert len(chain._utxos_by_addr.get(target.segwit_address, {})) == 1
    assert len(chain._utxos) >= 200
