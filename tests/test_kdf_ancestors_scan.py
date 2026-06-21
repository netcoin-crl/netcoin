"""Wallet KDF upgrade (#32), mempool ancestor limit (#9), gap-limit scan (#36)."""
import argparse
import json
from pathlib import Path

import pytest

from netcoin import cli
from netcoin import wallet as wallet_mod
from netcoin.chain import Blockchain, ChainError
from netcoin.params import MAX_MEMPOOL_ANCESTORS
from netcoin.tx import Transaction, TxInput, TxOutput, amount_to_sats
from netcoin.wallet import (
    Wallet,
    decrypt_private_key,
    encrypt_private_key,
)


# --- 32 KDF upgrade ---

def test_encrypt_uses_upgraded_iterations():
    enc = encrypt_private_key("ab" * 32, "pw")
    assert enc["iterations"] == str(wallet_mod.PBKDF2_ITERATIONS)
    assert wallet_mod.PBKDF2_ITERATIONS > wallet_mod.LEGACY_PBKDF2_ITERATIONS
    assert enc["cipher"] == "netcoin-hmac-stream-v2"
    assert decrypt_private_key(enc, "pw") == "ab" * 32


def test_legacy_250k_wallet_still_opens():
    # Build a v1-style payload at the legacy iteration count and confirm it decrypts.
    import hashlib, hmac, secrets

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", b"pw", salt, wallet_mod.LEGACY_PBKDF2_ITERATIONS, dklen=32)
    plaintext = ("cd" * 32).encode("ascii")
    ciphertext = wallet_mod._xor_stream(plaintext, key, nonce)
    mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    legacy = {
        "cipher": "netcoin-hmac-stream-v1",
        "iterations": "250000",
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "mac": mac.hex(),
    }
    assert decrypt_private_key(legacy, "pw") == "cd" * 32
    with pytest.raises(Exception):
        decrypt_private_key(legacy, "wrong")


def test_encrypted_wallet_roundtrip_file(tmp_path: Path):
    wallet = Wallet.create()
    path = tmp_path / "w.json"
    wallet.save(path, passphrase="hunter2")
    assert Wallet.load(path, passphrase="hunter2").private_key == wallet.private_key


# --- 9 mempool ancestor limit ---

def test_mempool_ancestor_limit(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)

    # Build a long unconfirmed chain off a single coinbase: tx0 spends coinbase,
    # tx1 spends tx0, ... each leaving a spendable change output back to miner.
    utxo = chain.utxos_for_address(miner.address)[0]
    prev_txid, prev_vout, prev_amount = utxo.txid, utxo.vout, utxo.output.amount
    fee = amount_to_sats("0.001")
    accepted = 0
    for _ in range(MAX_MEMPOOL_ANCESTORS + 5):
        out_amount = prev_amount - fee
        if out_amount <= amount_to_sats("0.01"):
            break
        tx = Transaction(
            inputs=[TxInput(txid=prev_txid, vout=prev_vout)],
            outputs=[TxOutput(amount=out_amount, address=miner.address)],
        )
        # sign against the prevout
        from netcoin.tx import SpendableOutput

        prevout = SpendableOutput(txid=prev_txid, vout=prev_vout, output=TxOutput(amount=prev_amount, address=miner.address), height=1)
        tx.sign_input(0, miner.private_key, prevout)
        try:
            chain.add_mempool_transaction(tx)
        except ChainError as exc:
            assert "too many unconfirmed ancestors" in str(exc)
            break
        accepted += 1
        prev_txid, prev_vout, prev_amount = tx.txid(), 0, out_amount
    # The chain was capped at the ancestor limit, not allowed to grow unbounded.
    assert accepted <= MAX_MEMPOOL_ANCESTORS


# --- 36 gap-limit scan ---

def test_wallet_scan_reports_activity(tmp_path: Path, capsys):
    _, phrase = Wallet.create_with_mnemonic()
    # Mine to index-0 address derived from the phrase so the scan sees activity.
    index0 = Wallet.create(seed_phrase=phrase, index=0)
    chain = Blockchain(tmp_path / "chain")
    chain.mine_block(index0.address)

    cli.cmd_wallet_scan(argparse.Namespace(data=str(tmp_path / "chain"), from_mnemonic=phrase, gap=3))
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert len(result["accounts"]) == 4  # indexes 0..3
    assert result["accounts"][0]["active"] is True
    assert result["active_accounts"] >= 1
