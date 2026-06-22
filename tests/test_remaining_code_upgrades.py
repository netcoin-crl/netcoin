"""Remaining v0.4.x code upgrades: headers-first sync, compact relay, witness
commitments, change rotation, wallet auto-lock, CAPTCHA hooks, and explorer
pagination."""
import argparse
import json
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from netcoin import cli
from netcoin.block import coinbase_witness_commitment, merkle_root, validate_witness_commitment
from netcoin.chain import Blockchain, ChainError
from netcoin.compact import CompactBlockError, make_compact_block, missing_transactions, reconstruct_compact_block
from netcoin.explorer_server import make_handler as make_explorer_handler
from netcoin.node import NetCoinNode, make_handler as make_node_handler
from netcoin.p2p import NetCoinP2PServer, sync_headers_first
from netcoin.tx import amount_to_sats
from netcoin.wallet import AutoLockWalletSession, Wallet, WalletError


class served_node:
    def __init__(self, node: NetCoinNode):
        self.node = node
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_node_handler(node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class served_explorer:
    def __init__(self, chain: Blockchain):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_explorer_handler(chain))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class served_p2p:
    def __init__(self, chain: Blockchain):
        self.server = NetCoinP2PServer(("127.0.0.1", 0), chain)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.host, self.port = self.server.server_address
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def get_json(url: str):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post_form(url: str, fields: dict):
    body = urlencode(fields).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(req, timeout=5) as response:
        return response.read().decode("utf-8")


def test_http_headers_first_sync_downloads_blocks_by_hash(tmp_path: Path):
    source = Blockchain(tmp_path / "source")
    target = Blockchain(tmp_path / "target")
    miner = Wallet.create()
    for _ in range(3):
        source.mine_block(miner.address)
    source_node = NetCoinNode(source, persist=False)
    target_node = NetCoinNode(target, persist=False)
    with served_node(source_node) as s:
        adopted = target_node.sync_from_peer(s.url)
    assert adopted is True
    assert target.tip_hash() == source.tip_hash()
    assert any(event["event"] == "headers_first_sync" for event in target_node.event_log)


def test_tcp_p2p_headers_first_sync_flow(tmp_path: Path):
    source = Blockchain(tmp_path / "source")
    target = Blockchain(tmp_path / "target")
    miner = Wallet.create()
    for _ in range(2):
        source.mine_block(miner.address)
    with served_p2p(source) as s:
        accepted = sync_headers_first(s.host, s.port, target)
    assert accepted == 2
    assert target.tip_hash() == source.tip_hash()


def test_compact_block_missing_transaction_request_flow(tmp_path: Path):
    source = Blockchain(tmp_path / "source")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        source.mine_block(miner.address)
    tx = miner.create_transaction(source, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    source.add_mempool_transaction(tx)
    source.mine_block(miner.address)
    block = source.tip()
    compact = make_compact_block(block)
    assert missing_transactions(compact, []) == [{"index": 1, "shortid": tx.txid()[:12]}]
    with pytest.raises(CompactBlockError):
        reconstruct_compact_block(compact, [])
    reconstructed = reconstruct_compact_block(compact, [], extra_transactions=[tx])
    assert reconstructed.hash() == block.hash()


def test_compact_block_missing_endpoint_returns_needed_txs(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    node = NetCoinNode(chain, persist=False)
    with served_node(node) as s:
        payload = get_json(f"{s.url}/compact-block-missing/{chain.tip_hash()}?have=")
    assert payload["block_hash"] == chain.tip_hash()
    assert payload["missing"][0]["txid"] == tx.txid()


def test_segwit_witness_commitment_required_for_witness_blocks(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.segwit_address)
    tx = miner.create_transaction(
        chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"), from_type="p2wpkh"
    )
    assert tx.has_witness
    chain.add_mempool_transaction(tx)
    block = chain.mine_block(miner.address)
    assert coinbase_witness_commitment(block) is not None
    assert validate_witness_commitment(block) is True
    # Removing the commitment makes the block invalid whenever non-coinbase witness data is present.
    tampered = block.to_dict()
    tampered["transactions"][0]["outputs"] = tampered["transactions"][0]["outputs"][:1]
    from netcoin.block import Block

    tampered_block = Block.from_dict(tampered)
    tampered_block.header.merkle_root = merkle_root(tampered_block.transactions)
    with pytest.raises(ChainError, match="witness commitment"):
        chain.validate_block_against(tampered_block, chain.chain[-2], chain.utxo_set(), chain.chain[:-1])


def test_change_address_rotation_persists_counter(tmp_path: Path, capsys):
    data = tmp_path / "chain"
    chain = Blockchain(data)
    miner = Wallet.create()
    receiver = Wallet.create()
    wallet_file = tmp_path / "miner.json"
    miner.save(wallet_file)
    for _ in range(101):
        chain.mine_block(miner.address)
    args = argparse.Namespace(
        data=str(data), wallet=str(wallet_file), passphrase=None, from_type="p2pkh", from_address=None,
        change_address=None, to=receiver.address, amount="1", fee="0.01", rbf=False, utxo=None,
        coin_strategy="greedy", rotate_change=True, broadcast_to=None,
    )
    cli.cmd_send(args)
    first = json.loads(capsys.readouterr().out)
    cli.cmd_send(args)
    second = json.loads(capsys.readouterr().out)
    saved = json.loads(wallet_file.read_text())
    assert first["change_rotated"] is True
    assert second["change_rotated"] is True
    assert first["change_address"] != second["change_address"]
    assert saved["change_index"] == 2


def test_auto_lock_wallet_session_expires(tmp_path: Path):
    wallet = Wallet.create()
    path = tmp_path / "wallet.json"
    wallet.save(path, passphrase="pw")
    session = AutoLockWalletSession(path, passphrase="pw", ttl_seconds=1)
    assert session.get_wallet().address == wallet.address
    time.sleep(1.2)
    assert session.locked is True
    with pytest.raises(WalletError, match="locked"):
        session.get_wallet()


def test_faucet_simple_captcha_hook(monkeypatch):
    import tools.faucet_server as faucet

    monkeypatch.setattr(faucet, "CAPTCHA_PROVIDER", "simple")
    monkeypatch.setattr(faucet, "CAPTCHA_SIMPLE_ANSWER", "netcoin")
    assert faucet.verify_captcha({"captcha": ["netcoin"]}, "127.0.0.1")[0] is True
    assert faucet.verify_captcha({"captcha": ["wrong"]}, "127.0.0.1")[0] is False
    assert "name=\"captcha\"" in faucet.captcha_html()


def test_explorer_latest_and_address_pagination(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(5):
        chain.mine_block(miner.address)
    with served_explorer(chain) as s:
        first_page = get_json(f"{s.url}/api/latest?limit=2&page=1")
        second_page = get_json(f"{s.url}/api/latest?limit=2&page=2")
        addr = get_json(f"{s.url}/api/address/{miner.address}?limit=2&offset=1")
    assert len(first_page["blocks"]) == 2
    assert len(second_page["blocks"]) == 2
    assert first_page["blocks"][0]["height"] == 5
    assert second_page["blocks"][0]["height"] == 3
    assert addr["limit"] == 2
    assert addr["offset"] == 1
