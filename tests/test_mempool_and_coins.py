"""Mempool expiry/eviction (#10) and coin-selection strategies (#34)."""

import time
from pathlib import Path

import pytest

from netcoin.chain import Blockchain
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet, WalletError, order_utxos_for_strategy


def funded(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    # Mine enough that several coinbase outputs are past the 100-block maturity.
    for _ in range(106):
        chain.mine_block(miner.address)
    return chain, miner, receiver


def add_spends(chain, miner, receiver, count):
    txids = []
    for utxo in chain.utxos_for_address(miner.address)[:count]:
        from netcoin.tx import Transaction, TxInput, TxOutput

        tx = Transaction(
            inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)],
            outputs=[TxOutput(amount=utxo.output.amount - amount_to_sats("0.01"), address=receiver.address)],
        )
        tx.sign_input(0, miner.private_key, utxo)
        txids.append(chain.add_mempool_transaction(tx))
    return txids


# --- 10 mempool expiry / eviction ---


def test_evict_expired_mempool(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    txids = add_spends(chain, miner, receiver, 3)
    assert chain.mempool_info()["size"] == 3
    # Backdate one tx well past the max age.
    chain.mempool_times[txids[0]] = time.time() - 10_000
    evicted = chain.evict_expired_mempool(max_age_seconds=3600)
    assert evicted == 1
    assert chain.mempool_info()["size"] == 2
    assert txids[0] not in {e["txid"] for e in chain.mempool_info()["entries"]}


def test_evict_mempool_to_size(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    add_spends(chain, miner, receiver, 4)
    assert chain.mempool_info()["size"] == 4
    dropped = chain.evict_mempool_to_size(2)
    assert dropped == 2
    assert chain.mempool_info()["size"] == 2
    # No-op when already within size.
    assert chain.evict_mempool_to_size(5) == 0


# --- 34 coin selection ---


def test_order_utxos_strategies(tmp_path: Path):
    chain, miner, _ = funded(tmp_path)
    utxos = chain.utxos_for_address(miner.address)
    largest = order_utxos_for_strategy(utxos, "largest-first")
    smallest = order_utxos_for_strategy(utxos, "smallest-first")
    amounts_l = [u.output.amount for u in largest]
    amounts_s = [u.output.amount for u in smallest]
    assert amounts_l == sorted(amounts_l, reverse=True)
    assert amounts_s == sorted(amounts_s)
    assert {u.outpoint() for u in largest} == {u.outpoint() for u in utxos}
    with pytest.raises(WalletError, match="unknown coin-selection"):
        order_utxos_for_strategy(utxos, "nonsense")


def test_send_with_strategy_builds_valid_tx(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    tx = miner.create_transaction(
        chain,
        receiver.address,
        amount_to_sats("1"),
        amount_to_sats("0.01"),
        strategy="largest-first",
    )
    chain.add_mempool_transaction(tx)
    assert chain.mempool_info()["size"] == 1
