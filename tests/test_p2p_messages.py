"""Bitcoin-style P2P message layer (#16): message types, framing, and handler flow."""

import argparse
import json
from pathlib import Path
from threading import Thread

from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.p2p import (
    Message,
    NetCoinP2PServer,
    block_message,
    getdata_message,
    getheaders_message,
    handle_message,
    inv_message,
    ping_message,
    read_block_message,
    read_tx_message,
    request_message,
    tx_message,
    verack_message,
    version_message,
)
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def roundtrip(msg: Message) -> Message:
    return Message.parse(msg.serialize())


def test_control_messages_frame_roundtrip():
    for msg in [
        version_message(5, genesis_hash="ab" * 32),
        verack_message(),
        ping_message(42),
        inv_message([{"type": "block", "hash": "aa"}]),
        getdata_message([{"type": "tx", "hash": "bb"}]),
        getheaders_message("cc"),
    ]:
        back = roundtrip(msg)
        assert back.command == msg.command
        assert back.payload == msg.payload


def test_block_and_tx_messages_carry_binary(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    block = chain.tip()

    bmsg = roundtrip(block_message(block))
    assert read_block_message(bmsg).hash() == block.hash()
    tmsg = roundtrip(tx_message(tx))
    assert read_tx_message(tmsg).txid() == tx.txid()


def test_handler_version_to_verack():
    assert handle_message(version_message(0)).command == "verack"


def test_handler_ping_to_pong_echoes_nonce():
    pong = handle_message(ping_message(12345))
    assert pong.command == "pong"
    import json

    assert json.loads(pong.payload)["nonce"] == 12345


def test_handler_getheaders_returns_headers(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)
    resp = handle_message(getheaders_message("0" * 64), chain)
    assert resp.command == "headers"
    import json

    headers = json.loads(resp.payload)["headers"]
    assert len(headers) == len(chain.chain)


def test_handler_inv_requests_getdata():
    resp = handle_message(inv_message([{"type": "block", "hash": "deadbeef"}]))
    assert resp.command == "getdata"
    import json

    assert json.loads(resp.payload)["inventory"][0]["hash"] == "deadbeef"


def test_handler_getdata_block_returns_block(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    tip_hash = chain.tip_hash()
    resp = handle_message(getdata_message([{"type": "block", "hash": tip_hash}]), chain)
    assert resp.command == "block"
    assert read_block_message(resp).hash() == tip_hash
    # Unknown hash -> no response.
    assert handle_message(getdata_message([{"type": "block", "hash": "0" * 64}]), chain) is None


def test_handshake_flow():
    # A minimal version/verack handshake exchange.
    a_version = version_message(0, genesis_hash="ab" * 32)
    b_response = handle_message(a_version)
    assert b_response.command == "verack"
    # Round-trips over the wire envelope too.
    assert Message.parse(b_response.serialize()).command == "verack"


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


def test_tcp_p2p_version_and_ping(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served_p2p(chain) as s:
        verack = request_message(s.host, s.port, version_message(chain.height(), genesis_hash=chain.chain[0].hash()))
        pong = request_message(s.host, s.port, ping_message(99))
    assert verack.command == "verack"
    assert pong.command == "pong"
    assert json.loads(pong.payload)["nonce"] == 99


def test_tcp_p2p_getheaders(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(2):
        chain.mine_block(miner.address)
    with served_p2p(chain) as s:
        response = request_message(s.host, s.port, getheaders_message(chain.chain[0].hash()))
    assert response.command == "headers"
    headers = json.loads(response.payload)["headers"]
    assert len(headers) == 3
    assert headers[-1]["hash"] == chain.tip_hash()


def test_tcp_p2p_accepts_block_message(tmp_path: Path):
    source = Blockchain(tmp_path / "source")
    target = Blockchain(tmp_path / "target")
    miner = Wallet.create()
    source.mine_block(miner.address)
    block = source.tip()
    with served_p2p(target) as s:
        response = request_message(s.host, s.port, block_message(block))
    assert response.command == "inv"
    assert target.tip_hash() == block.hash()


def test_cli_p2p_call_ping(tmp_path: Path, capsys):
    chain = Blockchain(tmp_path / "chain")
    with served_p2p(chain) as s:
        cli.cmd_p2p_call(
            argparse.Namespace(
                command="ping",
                host=s.host,
                port=s.port,
                timeout=5,
                height=0,
                genesis_hash="",
                nonce=123,
                locator="0" * 64,
            )
        )
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["command"] == "pong"
    assert result["payload"]["nonce"] == 123
