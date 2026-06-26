"""Wallet-DB format versioning + migration (#31)."""
import argparse
import json
from pathlib import Path

import pytest

from netcoin import cli
from netcoin import wallet as wallet_mod
from netcoin.wallet import (
    WALLET_FORMAT_VERSION,
    Wallet,
    wallet_file_version,
    wallet_needs_migration,
)


def test_new_wallets_stamp_version(tmp_path: Path):
    wallet = Wallet.create()
    path = tmp_path / "w.json"
    wallet.save(path)
    data = json.loads(path.read_text())
    assert data["wallet_version"] == WALLET_FORMAT_VERSION
    assert wallet_needs_migration(data) is False


def test_legacy_file_without_version_needs_migration():
    legacy = {"network": "NetCoin", "encrypted": False, "private_key_hex": "ab" * 32}
    assert wallet_file_version(legacy) == 1
    assert wallet_needs_migration(legacy) is True


def test_legacy_encrypted_low_kdf_needs_migration():
    data = {"wallet_version": 2, "encrypted": True,
            "encrypted_private_key": {
                "cipher": "netcoin-hmac-stream-v2",
                "iterations": str(wallet_mod.LEGACY_PBKDF2_ITERATIONS),
            }}
    assert wallet_needs_migration(data) is True


def test_migrate_plaintext_wallet_stamps_version(tmp_path: Path, capsys):
    wallet = Wallet.create()
    path = tmp_path / "w.json"
    # Write a legacy-style file with no version field.
    data = wallet.to_dict(passphrase=None)
    data.pop("wallet_version", None)
    path.write_text(json.dumps(data))
    assert wallet_needs_migration(json.loads(path.read_text())) is True

    cli.cmd_wallet_migrate(argparse.Namespace(wallet=str(path), passphrase=None))
    result = json.loads(capsys.readouterr().out)
    assert result["migrated"] is True
    assert result["to_version"] == WALLET_FORMAT_VERSION
    migrated = json.loads(path.read_text())
    assert migrated["wallet_version"] == WALLET_FORMAT_VERSION
    # The migrated wallet still opens and controls the same address.
    assert Wallet.load(path).address == wallet.address
    assert Path(result["backup_file"]).exists()


def test_migrate_reencrypts_legacy_kdf(tmp_path: Path, capsys):
    import hashlib, hmac, secrets

    wallet = Wallet.create()
    path = tmp_path / "enc.json"
    # Hand-build a v1-style encrypted wallet at the legacy 250k iteration count.
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", b"pw", salt, wallet_mod.LEGACY_PBKDF2_ITERATIONS, dklen=32)
    ct = wallet_mod._xor_stream(wallet.private_key_hex.encode("ascii"), key, nonce)
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    legacy = wallet.public_dict()
    legacy.update({
        "encrypted": True,
        "encrypted_private_key": {
            "cipher": "netcoin-hmac-stream-v1", "iterations": "250000",
            "salt": salt.hex(), "nonce": nonce.hex(), "ciphertext": ct.hex(), "mac": mac.hex(),
        },
    })
    path.write_text(json.dumps(legacy))
    assert wallet_needs_migration(json.loads(path.read_text())) is True

    cli.cmd_wallet_migrate(argparse.Namespace(wallet=str(path), passphrase="pw"))
    result = json.loads(capsys.readouterr().out)
    assert result["migrated"] is True and result["encrypted"] is True
    migrated = json.loads(path.read_text())
    # Re-encrypted at the upgraded KDF cost and stamped version.
    assert int(migrated["encrypted_private_key"]["iterations"]) == wallet_mod.PBKDF2_ITERATIONS
    assert migrated["encrypted_private_key"]["cipher"] == wallet_mod.AEAD_CIPHER
    assert migrated["encrypted_private_key"]["aead"] == "chacha20-poly1305"
    assert "mac" not in migrated["encrypted_private_key"]
    assert migrated["wallet_version"] == WALLET_FORMAT_VERSION
    assert Wallet.load(path, passphrase="pw").private_key == wallet.private_key


def test_migrate_noop_when_current(tmp_path: Path, capsys):
    wallet = Wallet.create()
    path = tmp_path / "w.json"
    wallet.save(path)  # already current
    cli.cmd_wallet_migrate(argparse.Namespace(wallet=str(path), passphrase=None))
    result = json.loads(capsys.readouterr().out)
    assert result["migrated"] is False
