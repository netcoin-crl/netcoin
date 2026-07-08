"""Coin control, seed confirmation, wallet unlock, and the label store."""

import argparse
import json
from pathlib import Path

import pytest

from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.labels import LabelStore
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet, WalletError, confirm_seed_phrase


def funded(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    return chain, miner, receiver


# --- 25 coin control ---


def test_coin_control_spends_only_chosen_utxo(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    utxos = chain.utxos_for_address(miner.address)
    chosen = utxos[1].outpoint()  # not the first one greedy-selection would pick
    tx = miner.create_transaction(
        chain,
        receiver.address,
        amount_to_sats("1"),
        amount_to_sats("0.01"),
        select_outpoints=[chosen],
    )
    assert len(tx.inputs) == 1
    assert tx.inputs[0].outpoint() == chosen
    chain.add_mempool_transaction(tx)


def test_coin_control_rejects_foreign_outpoint(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    with pytest.raises(WalletError, match="not spendable"):
        miner.create_transaction(
            chain,
            receiver.address,
            amount_to_sats("1"),
            amount_to_sats("0.01"),
            select_outpoints=[f"{'0' * 64}:0"],
        )


def test_coin_control_insufficient_selection(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    one = chain.utxos_for_address(miner.address)[0].outpoint()
    # One coinbase = 50 NET; ask for more than it covers.
    with pytest.raises(WalletError, match="do not cover"):
        miner.create_transaction(
            chain,
            receiver.address,
            amount_to_sats("100"),
            amount_to_sats("0.01"),
            select_outpoints=[one],
        )


# --- 21 seed confirmation ---


def test_confirm_seed_phrase_normalizes_whitespace():
    phrase = "net001 net002 net003"
    assert confirm_seed_phrase(phrase, "  net001   net002 net003 ") is True
    assert confirm_seed_phrase(phrase, "net001 net002") is False
    assert confirm_seed_phrase("", "") is False


# --- 22 wallet unlock ---


def test_wallet_unlock_verifies_and_decrypts(tmp_path: Path, capsys):
    wallet = Wallet.create()
    enc = tmp_path / "enc.json"
    wallet.save(enc, passphrase="pw")
    out = tmp_path / "plain.json"
    cli.cmd_wallet_unlock(argparse.Namespace(wallet=str(enc), passphrase="pw", out=str(out)))
    result = json.loads(capsys.readouterr().out)
    assert result["unlocked"] is True
    assert result["address"] == wallet.address
    reopened = Wallet.load(out)  # decrypted copy opens with no passphrase
    assert reopened.private_key == wallet.private_key


def test_wallet_unlock_wrong_passphrase(tmp_path: Path):
    wallet = Wallet.create()
    enc = tmp_path / "enc.json"
    wallet.save(enc, passphrase="pw")
    with pytest.raises(WalletError):
        cli.cmd_wallet_unlock(argparse.Namespace(wallet=str(enc), passphrase="nope", out=None))


# --- 26 labels / address book ---


def test_label_store_set_get_remove_persist(tmp_path: Path):
    path = tmp_path / "labels.json"
    store = LabelStore(path)
    store.set("Naddr1", "faucet")
    store.set("Naddr2", "miner")
    assert store.get("Naddr1") == "faucet"
    # Reload from disk.
    reloaded = LabelStore(path)
    assert reloaded.all() == {"Naddr1": "faucet", "Naddr2": "miner"}
    assert reloaded.remove("Naddr1") is True
    assert reloaded.remove("missing") is False
    assert LabelStore(path).get("Naddr1") is None


def test_label_cli(tmp_path: Path, capsys):
    labels = tmp_path / "labels.json"
    cli.cmd_label(argparse.Namespace(data=str(tmp_path), file=str(labels), set=["Nx", "mine"], get=None, remove=None))
    capsys.readouterr()
    cli.cmd_label(argparse.Namespace(data=str(tmp_path), file=str(labels), set=None, get="Nx", remove=None))
    assert json.loads(capsys.readouterr().out)["label"] == "mine"
