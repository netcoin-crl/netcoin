"""Taproot script-path (BIP341/342): tweak validated against the BIP341 vector,
script-tree commitment proofs, and a full hashlock script-path spend."""

import hashlib

from netcoin.chain import Blockchain
from netcoin.crypto import private_key_to_xonly_public_key
from netcoin.taproot import taproot_output, taproot_tweak, verify_script_path
from netcoin.tx import Transaction, TxInput, TxOutput
from netcoin.wallet import Wallet


def test_tweak_matches_bip341_vector():
    internal = bytes.fromhex("d6889cb081036e0faefa3a35157ad71086b123b2b144b649798b494c300a961d")
    out, _parity = taproot_tweak(internal, b"")
    assert out.hex() == "53a1f6e454df1aa2776a2814a721372d6258050de330b3c6d10ee8f4e0dda343"


def test_commitment_proofs_roundtrip():
    internal = bytes.fromhex("d6889cb081036e0faefa3a35157ad71086b123b2b144b649798b494c300a961d")
    scripts = ["OP_SHA256 aa OP_EQUAL", "02ab OP_CHECKSIG", "OP_DROP OP_1", "OP_1"]
    info = taproot_output(internal, scripts)
    out = bytes.fromhex(info["output_key"])
    for s in scripts:
        assert verify_script_path(out, s.encode(), bytes.fromhex(info["control_blocks"][s])) is True
    # a script not in the tree fails even with a real leaf's control block
    assert verify_script_path(out, b"OP_RETURN evil", bytes.fromhex(info["control_blocks"][scripts[0]])) is False


def _funded_hashlock(tmp_path, preimage: bytes, extra_leaf="OP_DROP OP_1"):
    w = Wallet.create()
    internal = private_key_to_xonly_public_key(w.private_key)
    leaf = f"OP_SHA256 {hashlib.sha256(preimage).hexdigest()} OP_EQUAL"
    info = taproot_output(internal, [leaf, extra_leaf])
    chain = Blockchain(tmp_path / "c")
    for _ in range(103):
        chain.mine_block(info["address"])
    utxo = chain.utxos_for_address(info["address"])[0]
    return utxo, leaf, info["control_blocks"][leaf]


def _spend(utxo, witness):
    dest = Wallet.create().address_for("legacy")
    tx = Transaction(
        inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)], outputs=[TxOutput(amount=100, address=dest)], locktime=0
    )
    tx.inputs[0].witness = witness
    return tx.verify_input(0, utxo)


def test_script_path_hashlock_spend(tmp_path):
    preimage = b"open sesame"
    utxo, leaf, control = _funded_hashlock(tmp_path, preimage)
    assert _spend(utxo, [preimage.hex(), leaf.encode().hex(), control]) is True


def test_script_path_wrong_preimage_rejected(tmp_path):
    utxo, leaf, control = _funded_hashlock(tmp_path, b"open sesame")
    assert _spend(utxo, [b"nope".hex(), leaf.encode().hex(), control]) is False


def test_script_path_tampered_control_rejected(tmp_path):
    preimage = b"open sesame"
    utxo, leaf, control = _funded_hashlock(tmp_path, preimage)
    bad = control[:-2] + ("00" if control[-2:] != "00" else "11")
    assert _spend(utxo, [preimage.hex(), leaf.encode().hex(), bad]) is False


def test_uncommitted_leaf_rejected(tmp_path):
    preimage = b"open sesame"
    utxo, _leaf, control = _funded_hashlock(tmp_path, preimage)
    # a valid script that isn't the committed leaf must not pass with that control block
    assert _spend(utxo, [b"x".hex(), b"OP_DROP OP_1 OP_1".hex(), control]) is False


def test_keypath_taproot_still_works(tmp_path):
    chain = Blockchain(tmp_path / "c")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.taproot_address)
    from netcoin.tx import amount_to_sats

    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="taproot"
    )
    assert len(tx.inputs[0].witness) == 1  # single Schnorr sig = key-path
    chain.add_mempool_transaction(tx)
