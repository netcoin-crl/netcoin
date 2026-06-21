"""Wallet safety: seed-phrase verification, recovery round-trips, encryption."""
import json
from pathlib import Path

import pytest

from netcoin.wallet import (
    Wallet,
    WalletError,
    new_seed_phrase,
    verify_seed_phrase,
)


def test_seed_phrase_recovery_round_trip():
    wallet, phrase = Wallet.create_with_mnemonic()
    restored = Wallet.from_mnemonic(phrase)
    assert restored.private_key == wallet.private_key
    assert restored.address == wallet.address


def test_verify_seed_phrase_accepts_valid_rejects_garbage():
    _, phrase = Wallet.create_with_mnemonic()
    assert verify_seed_phrase(phrase) is True
    assert verify_seed_phrase("not a real phrase") is False
    assert verify_seed_phrase("") is False
    # A valid phrase with its checksum word corrupted must fail.
    words = phrase.split()
    bad_checksum = " ".join(words[:-1] + ["net000" if words[-1] != "net000" else "net001"])
    assert verify_seed_phrase(bad_checksum) is False


def test_matches_seed_phrase_confirms_backup():
    wallet, phrase = Wallet.create_with_mnemonic()
    assert wallet.matches_seed_phrase(phrase) is True

    # A different valid phrase must not match this wallet.
    other_phrase = new_seed_phrase()
    while other_phrase == phrase:
        other_phrase = new_seed_phrase()
    assert wallet.matches_seed_phrase(other_phrase) is False

    # An invalid phrase returns False rather than raising.
    assert wallet.matches_seed_phrase("garbage words here") is False


def test_encrypted_wallet_round_trip_and_wrong_passphrase(tmp_path: Path):
    wallet = Wallet.create()
    path = tmp_path / "enc-wallet.json"
    wallet.save(path, passphrase="correct horse")

    # File must not contain the plaintext private key.
    raw = path.read_text()
    assert wallet.private_key_hex not in raw
    assert '"encrypted": true' in raw.lower()

    reopened = Wallet.load(path, passphrase="correct horse")
    assert reopened.private_key == wallet.private_key

    with pytest.raises(WalletError, match="passphrase is incorrect|modified"):
        Wallet.load(path, passphrase="wrong passphrase")


def test_tampered_encrypted_wallet_is_rejected(tmp_path: Path):
    wallet = Wallet.create()
    path = tmp_path / "enc-wallet.json"
    wallet.save(path, passphrase="pw")

    data = json.loads(path.read_text())
    ct = data["encrypted_private_key"]["ciphertext"]
    # Flip the first nibble of the ciphertext.
    data["encrypted_private_key"]["ciphertext"] = ("1" if ct[0] == "0" else "0") + ct[1:]
    path.write_text(json.dumps(data))

    with pytest.raises(WalletError, match="incorrect or file was modified"):
        Wallet.load(path, passphrase="pw")


def test_plaintext_wallet_address_must_match_key(tmp_path: Path):
    wallet = Wallet.create()
    data = wallet.to_dict(passphrase=None)
    data["address"] = "NotTheRightAddress"
    with pytest.raises(WalletError, match="address does not match"):
        Wallet.from_dict(data)
