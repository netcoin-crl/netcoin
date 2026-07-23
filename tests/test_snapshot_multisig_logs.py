"""UTXO snapshot (#23), multisig address (#26), structured logging (#19),
explorer mempool section (#43)."""

import argparse
import json
from pathlib import Path

from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.explorer import generate_explorer
from netcoin.logsetup import json_logging_enabled, structured_log
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def funded(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    return chain, miner, receiver


# --- 23 UTXO snapshot ---


def test_utxo_snapshot_export_and_verify(tmp_path: Path):
    chain, _miner, _ = funded(tmp_path)
    snap = chain.export_utxo_snapshot()
    assert snap["height"] == 101
    assert snap["utxo_count"] == len(snap["utxos"])
    assert chain.verify_utxo_snapshot(snap) is True
    # Digest is deterministic.
    assert chain.utxo_snapshot_digest() == snap["digest"]


def test_utxo_snapshot_detects_change(tmp_path: Path):
    chain, miner, _receiver = funded(tmp_path)
    snap = chain.export_utxo_snapshot()
    chain.mine_block(miner.address)  # changes the UTXO set + tip
    assert chain.verify_utxo_snapshot(snap) is False


def test_utxo_snapshot_cli_writes_file(tmp_path: Path, capsys):
    _chain, _miner, _ = funded(tmp_path)
    out = tmp_path / "snap.json"
    cli.cmd_utxo_snapshot(argparse.Namespace(data=str(tmp_path / "chain"), out=str(out)))
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert "utxos" not in result  # summary only
    assert json.loads(out.read_text())["digest"] == result["digest"]


# --- 26 multisig ---


def test_multisig_address_cli(tmp_path: Path, capsys):
    keys = [Wallet.create().public_key_hex for _ in range(3)]
    cli.cmd_multisig_address(argparse.Namespace(required=2, pubkey=keys))
    result = json.loads(capsys.readouterr().out)
    assert result["type"] == "2-of-3 multisig"
    assert result["address"]
    assert result["redeem_script"]
    assert result["required"] == 2


# --- 19 structured logging ---


def test_structured_log_is_valid_json():
    line = structured_log("block_accepted", component="node", hash="abc", height=5)
    record = json.loads(line)
    assert record["event"] == "block_accepted"
    assert record["component"] == "node"
    assert record["hash"] == "abc" and record["height"] == 5
    assert "ts" in record


def test_json_logging_toggle(monkeypatch):
    monkeypatch.delenv("NETCOIN_LOG_JSON", raising=False)
    assert json_logging_enabled() is False
    monkeypatch.setenv("NETCOIN_LOG_JSON", "1")
    assert json_logging_enabled() is True


# --- 43 explorer mempool section ---


def test_explorer_shows_mempool(tmp_path: Path):
    chain, miner, receiver = funded(tmp_path)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    out = tmp_path / "explorer"
    generate_explorer(chain, out)
    html = (out / "index.html").read_text()
    assert "Mempool (1 unconfirmed" in html
    assert tx.txid() in html
