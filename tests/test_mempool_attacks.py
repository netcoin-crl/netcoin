"""Mempool policy / attack-surface tests: dust, low fee, duplicate inputs,
over-weight, and RBF conflict handling."""
from pathlib import Path

import pytest

import netcoin.chain as chain_module
from netcoin.chain import Blockchain, ChainError
from netcoin.tx import SpendableOutput, Transaction, TransactionError, TxInput, TxOutput, amount_to_sats
from netcoin.wallet import Wallet


def funded(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    return chain, miner, receiver


def test_dust_output_is_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    # 100 sats is below the 546-sat dust threshold.
    tx = miner.create_transaction(chain, receiver.address, 100, amount_to_sats("0.01"))
    with pytest.raises(ChainError, match="dust"):
        chain.add_mempool_transaction(tx)
    assert chain.mempool_info()["size"] == 0


def test_fee_below_min_relay_is_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), 0)
    with pytest.raises(ChainError, match="below min relay fee"):
        chain.add_mempool_transaction(tx)


def test_duplicate_input_outpoint_is_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    utxo = chain.utxos_for_address(miner.address)[0]
    tx = Transaction(
        inputs=[TxInput(txid=utxo.txid, vout=utxo.vout), TxInput(txid=utxo.txid, vout=utxo.vout)],
        outputs=[TxOutput(amount=amount_to_sats("1"), address=receiver.address)],
    )
    tx.sign_input(0, miner.private_key, utxo)
    tx.sign_input(1, miner.private_key, utxo)
    with pytest.raises((ChainError, TransactionError), match="same outpoint"):
        chain.add_mempool_transaction(tx)


def test_overweight_transaction_is_rejected(tmp_path: Path, monkeypatch):
    chain, miner, receiver = funded(tmp_path)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    # Shrink the standard-weight ceiling so any real tx is non-standard.
    monkeypatch.setattr(chain_module, "MAX_STANDARD_TX_WEIGHT", 1)
    with pytest.raises(ChainError, match="weight too high"):
        chain.add_mempool_transaction(tx)


def test_conflicting_non_rbf_is_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    a = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    b = miner.create_transaction(chain, receiver.address, amount_to_sats("2"), amount_to_sats("0.01"))
    assert a.inputs[0].outpoint() == b.inputs[0].outpoint()
    chain.add_mempool_transaction(a)
    with pytest.raises(ChainError, match="non-replaceable"):
        chain.add_mempool_transaction(b)
    assert chain.mempool_info()["size"] == 1


def test_rbf_replacement_requires_higher_fee(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    original = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), rbf=True)
    chain.add_mempool_transaction(original)
    assert original.signals_rbf

    # Same inputs and same fee, but a distinct tx (different amount) -> rejected
    # because the replacement fee is not higher.
    same_fee = miner.create_transaction(chain, receiver.address, amount_to_sats("1.5"), amount_to_sats("0.01"), rbf=True)
    assert same_fee.txid() != original.txid()
    assert same_fee.inputs[0].outpoint() == original.inputs[0].outpoint()
    with pytest.raises(ChainError, match="replacement fee is not higher"):
        chain.add_mempool_transaction(same_fee)

    # Same inputs, higher fee -> replaces the original.
    higher_fee = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.05"), rbf=True)
    chain.add_mempool_transaction(higher_fee)
    txids = {e["txid"] for e in chain.mempool_info()["entries"]}
    assert higher_fee.txid() in txids
    assert original.txid() not in txids



def test_rbf_replacement_requires_incremental_relay_fee(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    original_fee = amount_to_sats("0.01")
    original = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), original_fee, rbf=True)
    chain.add_mempool_transaction(original)

    # One extra satoshi is higher in absolute terms, but does not pay the
    # incremental relay fee required to compensate peers for replacing the
    # original transaction in their mempools.
    tiny_bump = miner.create_transaction(chain, receiver.address, amount_to_sats("1.5"), original_fee + 1, rbf=True)
    assert tiny_bump.inputs[0].outpoint() == original.inputs[0].outpoint()
    with pytest.raises(ChainError, match="incremental relay fee"):
        chain.add_mempool_transaction(tiny_bump)

def test_mempool_accepts_many_independent_transactions(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    # Each mined coinbase is a separate spendable UTXO; spend several independently.
    count = 0
    for utxo in chain.utxos_for_address(miner.address)[:5]:
        tx = Transaction(
            inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)],
            outputs=[TxOutput(amount=utxo.output.amount - amount_to_sats("0.01"), address=receiver.address)],
        )
        tx.sign_input(0, miner.private_key, utxo)
        chain.add_mempool_transaction(tx)
        count += 1
    assert chain.mempool_info()["size"] == count


def test_package_relay_allows_child_pays_for_parent(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    final = Wallet.create()

    # Parent intentionally pays zero fee, so it is valid by consensus but not
    # acceptable as a standalone mempool transaction under min-relay policy.
    parent = miner.create_transaction(chain, receiver.address, amount_to_sats("2"), 0)
    with pytest.raises(ChainError, match="below min relay fee"):
        chain.add_mempool_transaction(parent)

    parent_output = parent.outputs[0]
    child_fee = 10_000
    child = Transaction(
        inputs=[TxInput(txid=parent.txid(), vout=0)],
        outputs=[TxOutput(amount=parent_output.amount - child_fee, address=final.address)],
    )
    child.sign_input(0, receiver.private_key, SpendableOutput(parent.txid(), 0, parent_output, height=None, coinbase=False))

    txids = chain.add_mempool_package([parent, child])
    assert txids == [parent.txid(), child.txid()]
    info = chain.mempool_info()
    assert info["size"] == 2
    assert any(pkg["count"] == 2 and set(pkg["txids"]) == set(txids) for pkg in info["packages"])
