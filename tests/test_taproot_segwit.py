"""Deeper Taproot/SegWit spend coverage (#29): key-path spends, witness tamper,
and Schnorr sign/verify edges."""

from pathlib import Path

import pytest

from netcoin.chain import Blockchain, ChainError
from netcoin.crypto import (
    private_key_to_xonly_public_key,
    schnorr_sign,
    schnorr_verify,
)
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def funded(tmp_path: Path, address_attr: str):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    addr = getattr(miner, address_attr)
    for _ in range(101):
        chain.mine_block(addr)
    return chain, miner, receiver


# --- round-trip spends per address type ---


def test_taproot_keypath_spend(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path, "taproot_address")
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="taproot"
    )
    assert tx.has_witness and len(tx.inputs[0].witness) == 1  # single Schnorr sig
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    assert chain.balances_for_address(receiver.address)["total"] == amount_to_sats("1")


def test_segwit_p2wpkh_spend(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path, "segwit_address")
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="segwit"
    )
    assert len(tx.inputs[0].witness) == 2  # sig + pubkey
    chain.add_mempool_transaction(tx)
    assert chain.mempool_info()["size"] == 1


def test_p2sh_segwit_spend(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path, "p2sh_segwit_address")
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="p2sh-segwit"
    )
    # Nested P2SH-P2WPKH: sig+pubkey in the witness, P2WPKH redeem script in scriptSig.
    assert len(tx.inputs[0].witness) == 2
    assert tx.inputs[0].script_sig.startswith("OP_0 ")
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    assert chain.balances_for_address(receiver.address)["total"] == amount_to_sats("1")


# --- witness tampering is rejected ---


def test_tampered_taproot_signature_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path, "taproot_address")
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="taproot"
    )
    sig = tx.inputs[0].witness[0]
    tx.inputs[0].witness[0] = ("1" if sig[0] == "0" else "0") + sig[1:]  # corrupt the Schnorr sig
    with pytest.raises(ChainError, match="signature"):
        chain.add_mempool_transaction(tx)


def test_tampered_segwit_pubkey_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path, "segwit_address")
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="segwit"
    )
    # Replace the witness pubkey with a different wallet's key (hash160 won't match).
    tx.inputs[0].witness[1] = Wallet.create().public_key_hex
    with pytest.raises(ChainError, match="signature"):
        chain.add_mempool_transaction(tx)


def test_tampered_p2sh_segwit_pubkey_rejected(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path, "p2sh_segwit_address")
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="p2sh-segwit"
    )
    # Swap in a different wallet's pubkey: its hash160 won't match the redeem script.
    tx.inputs[0].witness[1] = Wallet.create().public_key_hex
    with pytest.raises(ChainError, match="signature"):
        chain.add_mempool_transaction(tx)


# --- Schnorr primitive edges ---


def test_schnorr_sign_verify_roundtrip_and_failures():
    w = Wallet.create()
    xonly = private_key_to_xonly_public_key(w.private_key)
    digest = b"\x11" * 32
    sig = schnorr_sign(w.private_key, digest)
    assert schnorr_verify(xonly, digest, sig) is True
    # Wrong message fails.
    assert schnorr_verify(xonly, b"\x22" * 32, sig) is False
    # Wrong key fails.
    other = private_key_to_xonly_public_key(Wallet.create().private_key)
    assert schnorr_verify(other, digest, sig) is False
    # Tampered signature fails.
    bad = bytearray(sig)
    bad[0] ^= 0x01
    assert schnorr_verify(xonly, digest, bytes(bad)) is False
