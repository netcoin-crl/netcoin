from pathlib import Path

import pytest

from netcoin.chain import Blockchain, ChainError
from netcoin.fee_bump import create_cpfp_child, create_rbf_replacement, transaction_fee
from netcoin.tx import SpendableOutput, TxOutput, amount_to_sats
from netcoin.wallet import Wallet, WalletError


def funded(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    return chain, miner, receiver


def test_rbf_replacement_reduces_change_and_replaces_mempool_entry(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    original_fee = amount_to_sats("0.01")
    bumped_fee = amount_to_sats("0.05")
    original = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), original_fee, rbf=True)
    prevouts = [chain.utxo_set()[txin.outpoint()] for txin in original.inputs]
    chain.add_mempool_transaction(original)

    plan = create_rbf_replacement(miner, original, prevouts, new_fee=bumped_fee, change_address=miner.address)
    assert plan.method == "rbf"
    assert plan.replacement.signals_rbf
    assert transaction_fee(plan.replacement, prevouts) == bumped_fee

    chain.add_mempool_transaction(plan.replacement)
    txids = {entry["txid"] for entry in chain.mempool_info()["entries"]}
    assert plan.replacement.txid() in txids
    assert original.txid() not in txids


def test_rbf_replacement_refuses_non_replaceable_transaction(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    original = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    prevouts = [chain.utxo_set()[txin.outpoint()] for txin in original.inputs]
    with pytest.raises(WalletError, match="does not signal RBF"):
        create_rbf_replacement(miner, original, prevouts, new_fee=amount_to_sats("0.02"))


def test_cpfp_child_can_package_low_fee_parent(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    final = Wallet.create()
    parent = miner.create_transaction(chain, receiver.address, amount_to_sats("2"), 0)
    with pytest.raises(ChainError, match="below min relay fee"):
        chain.add_mempool_transaction(parent)

    child_fee = 10_000
    plan = create_cpfp_child(receiver, parent, parent_vout=0, fee=child_fee, destination_address=final.address)
    assert plan.method == "cpfp"
    assert plan.replacement.inputs[0].txid == parent.txid()
    txids = chain.add_mempool_package([parent, plan.replacement])
    assert txids == [parent.txid(), plan.replacement.txid()]
