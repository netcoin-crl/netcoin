"""Multiple SIGHASH types (consensus Item 1): ALL/NONE/SINGLE + ANYONECANPAY.
ALL stays the default and byte-identical; the other modes commit to subsets of the
transaction so it can be partially modified after signing."""

from pathlib import Path

import pytest

from netcoin.chain import Blockchain
from netcoin.tx import (
    SIGHASH_ALL,
    SIGHASH_ANYONECANPAY,
    SIGHASH_NONE,
    SIGHASH_SINGLE,
    Transaction,
    TransactionError,
    TxInput,
    TxOutput,
)
from netcoin.wallet import Wallet


def _funded(tmp_path: Path, address_attr: str):
    chain = Blockchain(tmp_path / "c")
    w = Wallet.create()
    addr = getattr(w, address_attr)
    for _ in range(103):
        chain.mine_block(addr)
    return chain, w, chain.utxos_for_address(addr)


def _tx(utxo, outs):
    return Transaction(
        inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)],
        outputs=[TxOutput(amount=a, address=ad) for a, ad in outs],
        locktime=0,
    )


def _reout(signed, outs):
    return Transaction(inputs=signed.inputs, outputs=[TxOutput(amount=a, address=ad) for a, ad in outs], locktime=0)


@pytest.mark.parametrize("attr,dest_kind", [("address", "legacy"), ("segwit_address", "segwit")])
def test_all_roundtrip_and_tamper(tmp_path, attr, dest_kind):
    chain, w, utxos = _funded(tmp_path, attr)
    dest = Wallet.create().address_for(dest_kind)
    me = w.address_for(dest_kind)
    tx = _tx(utxos[0], [(100, dest), (200, me)])
    tx.sign_input(0, w.private_key, utxos[0])  # default ALL
    assert tx.verify_input(0, utxos[0]) is True
    # ALL commits to outputs, so any output change invalidates
    assert _reout(tx, [(999, dest), (200, me)]).verify_input(0, utxos[0]) is False


@pytest.mark.parametrize("attr,dest_kind", [("address", "legacy"), ("segwit_address", "segwit")])
def test_none_does_not_commit_outputs(tmp_path, attr, dest_kind):
    chain, w, utxos = _funded(tmp_path, attr)
    dest = Wallet.create().address_for(dest_kind)
    me = w.address_for(dest_kind)
    tx = _tx(utxos[0], [(100, dest), (200, me)])
    tx.sign_input(0, w.private_key, utxos[0], SIGHASH_NONE)
    assert tx.verify_input(0, utxos[0]) is True
    assert _reout(tx, [(999, dest), (50, me)]).verify_input(0, utxos[0]) is True  # outputs free


@pytest.mark.parametrize("attr,dest_kind", [("address", "legacy"), ("segwit_address", "segwit")])
def test_single_commits_only_same_index_output(tmp_path, attr, dest_kind):
    chain, w, utxos = _funded(tmp_path, attr)
    dest = Wallet.create().address_for(dest_kind)
    me = w.address_for(dest_kind)
    tx = _tx(utxos[0], [(100, dest), (200, me)])
    tx.sign_input(0, w.private_key, utxos[0], SIGHASH_SINGLE)
    assert tx.verify_input(0, utxos[0]) is True
    assert _reout(tx, [(100, dest), (999, me)]).verify_input(0, utxos[0]) is True  # other output free
    assert _reout(tx, [(999, dest), (200, me)]).verify_input(0, utxos[0]) is False  # paired output pinned


def test_single_without_matching_output_is_invalid(tmp_path):
    chain, w, utxos = _funded(tmp_path, "segwit_address")
    # input index 1 but only one output -> SIGHASH_SINGLE has no pair
    tx = Transaction(
        inputs=[TxInput(txid=utxos[0].txid, vout=utxos[0].vout), TxInput(txid=utxos[1].txid, vout=utxos[1].vout)],
        outputs=[TxOutput(amount=100, address=w.segwit_address)],
        locktime=0,
    )
    tx.sign_input(0, w.private_key, utxos[0], SIGHASH_SINGLE)  # index 0 has output 0: fine
    with pytest.raises(TransactionError):
        tx.sign_input(1, w.private_key, utxos[1], SIGHASH_SINGLE)  # index 1 has no output


def test_anyonecanpay_allows_adding_inputs(tmp_path):
    chain, w, utxos = _funded(tmp_path, "address")
    dest = Wallet.create().address_for("legacy")
    tx = _tx(utxos[0], [(100, dest), (200, w.address)])
    tx.sign_input(0, w.private_key, utxos[0], SIGHASH_ALL | SIGHASH_ANYONECANPAY)
    assert tx.verify_input(0, utxos[0]) is True
    tx.inputs.append(TxInput(txid=utxos[1].txid, vout=utxos[1].vout))  # add a second input
    assert tx.verify_input(0, utxos[0]) is True  # first input's signature survives


def test_unknown_sighash_type_rejected(tmp_path):
    chain, w, utxos = _funded(tmp_path, "segwit_address")
    tx = _tx(utxos[0], [(100, w.segwit_address)])
    with pytest.raises(TransactionError):
        tx.sighash(0, utxos[0], 0x09)  # not a valid base type
