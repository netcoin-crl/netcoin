"""CLI wallet commands: backup, recovery test, watch-only export, key-export guard."""

import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import AEAD_CIPHER, PBKDF2_ITERATIONS, Wallet, WalletError, new_seed_phrase


def make_wallet(tmp_path: Path):
    wallet, phrase = Wallet.create_with_mnemonic()
    path = tmp_path / "wallet.json"
    wallet.save(path)
    return wallet, phrase, path


def test_wallet_backup_creates_timestamped_copy(tmp_path: Path, capsys):
    _, _, path = make_wallet(tmp_path)
    out_dir = tmp_path / "backups"
    cli.cmd_wallet_backup(argparse.Namespace(wallet=str(path), out_dir=str(out_dir)))
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    backup = Path(result["backup_file"])
    assert backup.exists()
    assert backup.read_text() == path.read_text()


def test_wallet_recover_test_matches(tmp_path: Path, capsys):
    wallet, phrase, path = make_wallet(tmp_path)
    cli.cmd_wallet_recover_test(
        argparse.Namespace(from_mnemonic=phrase, wallet=str(path), address=None, passphrase=None)
    )
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["recovered_address"] == wallet.address


def test_wallet_recover_test_detects_wrong_phrase(tmp_path: Path):
    _wallet, phrase, path = make_wallet(tmp_path)
    other = new_seed_phrase()
    while other == phrase:
        other = new_seed_phrase()
    with pytest.raises(SystemExit):
        cli.cmd_wallet_recover_test(
            argparse.Namespace(from_mnemonic=other, wallet=str(path), address=None, passphrase=None)
        )


def test_wallet_export_watch_has_no_private_key(tmp_path: Path, capsys):
    wallet, _, path = make_wallet(tmp_path)
    out = tmp_path / "watch.json"
    cli.cmd_wallet_export_watch(argparse.Namespace(wallet=str(path), passphrase=None, out=str(out)))
    capsys.readouterr()
    data = json.loads(out.read_text())
    assert data.get("address") == wallet.address
    assert "private_key_hex" not in json.dumps(data)
    assert wallet.private_key_hex not in out.read_text()


def test_wallet_info_refuses_private_key_without_ack(tmp_path: Path):
    _, _, path = make_wallet(tmp_path)
    with pytest.raises(WalletError, match="i-understand-export-risk"):
        cli.cmd_wallet_info(
            argparse.Namespace(wallet=str(path), passphrase=None, show_private=True, i_understand_export_risk=False)
        )


def test_wallet_info_shows_private_key_with_ack(tmp_path: Path, capsys):
    wallet, _, path = make_wallet(tmp_path)
    cli.cmd_wallet_info(
        argparse.Namespace(wallet=str(path), passphrase=None, show_private=True, i_understand_export_risk=True)
    )
    result = json.loads(capsys.readouterr().out)
    assert result["private_key_hex"] == wallet.private_key_hex
    assert "export_warning" in result


def test_wallet_info_reports_encrypted_file_metadata(tmp_path: Path, capsys):
    wallet = Wallet.create()
    path = tmp_path / "encrypted.json"
    wallet.save(path, passphrase="pw")

    cli.cmd_wallet_info(
        argparse.Namespace(wallet=str(path), passphrase="pw", show_private=False, i_understand_export_risk=False)
    )
    result = json.loads(capsys.readouterr().out)
    assert result["address"] == wallet.address
    assert result["encrypted"] is True
    assert result["encryption_cipher"] == AEAD_CIPHER
    assert result["encryption_aead"] == "chacha20-poly1305"
    assert result["encryption_iterations"] == str(PBKDF2_ITERATIONS)
    assert "private_key_hex" not in result
    assert "encrypted_private_key" not in result


def test_balance_can_query_remote_node(tmp_path: Path, capsys):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(NetCoinNode(chain, persist=False)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cli.cmd_balance(
            argparse.Namespace(
                data=str(tmp_path / "unused"),
                wallet=None,
                address=miner.address,
                address_type="p2pkh",
                passphrase=None,
                node=f"http://127.0.0.1:{server.server_address[1]}",
            )
        )
        result = json.loads(capsys.readouterr().out)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert result["address"] == miner.address
    assert result["height"] == 1
    assert result["total"] == "50.00000000"
