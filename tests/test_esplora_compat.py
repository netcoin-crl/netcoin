"""Esplora-compatibility layer: response shapes match Blockstream Esplora.

Drives the real node handler end-to-end so the /esplora/* surface is proven,
not just the pure mappers.
"""

import json

import pytest

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import Wallet


class _FakeWFile:
    def __init__(self):
        self.chunks = []

    def write(self, b):
        self.chunks.append(b)


class _Capture:
    """Minimal driver that calls the node Handler's _handle_esplora directly."""

    def __init__(self, node):
        Handler = make_handler(node)
        self.node = node
        self.Handler = Handler

    def get(self, path):
        from urllib.parse import urlparse

        node = self.node
        Handler = self.Handler
        captured = {}

        class H(Handler):
            def __init__(self):  # bypass BaseHTTPRequestHandler socket setup
                self.wfile = _FakeWFile()

            def send_response(self, code, *a):
                captured["status"] = code

            def send_header(self, *a, **k):
                pass

            def end_headers(self):
                pass

        h = H()
        h._handle_esplora(urlparse(path), node)
        body = b"".join(h.wfile.chunks).decode("utf-8")
        return captured.get("status", 200), body


@pytest.fixture
def node(tmp_path):
    chain = Blockchain(tmp_path / "chain")
    w = Wallet.create()
    for _ in range(3):
        chain.mine_block(w.address)
    n = NetCoinNode(chain, persist=False)
    n._test_address = w.address
    return n


def test_esplora_tip_endpoints(node):
    drv = _Capture(node)
    status, height = drv.get("/esplora/blocks/tip/height")
    assert status == 200 and int(height) == node.chain.height()
    status, tiphash = drv.get("/esplora/blocks/tip/hash")
    assert status == 200 and tiphash == node.chain.tip_hash()


def test_esplora_block_and_block_height(node):
    drv = _Capture(node)
    _, h = drv.get("/esplora/block-height/1")
    assert h == node.chain.chain[1].hash()
    status, body = drv.get(f"/esplora/block/{h}")
    assert status == 200
    block = json.loads(body)
    # Esplora block shape
    for key in ("id", "height", "version", "timestamp", "tx_count", "merkle_root", "previousblockhash"):
        assert key in block
    assert block["id"] == h and block["height"] == 1


def test_esplora_tx_shape(node):
    drv = _Capture(node)
    txid = node.chain.chain[1].transactions[0].txid()
    status, body = drv.get(f"/esplora/tx/{txid}")
    assert status == 200
    tx = json.loads(body)
    for key in ("txid", "version", "locktime", "vin", "vout", "status"):
        assert key in tx
    assert tx["txid"] == txid
    assert tx["status"]["confirmed"] is True
    assert tx["status"]["block_height"] == 1
    # coinbase vin is flagged; vout carries address + value
    assert tx["vin"][0]["is_coinbase"] is True
    assert tx["vout"][0]["value"] > 0
    assert tx["vout"][0]["scriptpubkey_address"]


def test_esplora_address_and_utxo(node):
    drv = _Capture(node)
    addr = node._test_address
    status, body = drv.get(f"/esplora/address/{addr}")
    assert status == 200
    a = json.loads(body)
    assert a["address"] == addr
    for key in ("funded_txo_count", "funded_txo_sum", "spent_txo_count", "spent_txo_sum", "tx_count"):
        assert key in a["chain_stats"]
    assert "mempool_stats" in a

    status, body = drv.get(f"/esplora/address/{addr}/utxo")
    assert status == 200
    utxos = json.loads(body)
    assert isinstance(utxos, list)
    for u in utxos:
        assert {"txid", "vout", "value", "status"}.issubset(u.keys())


def test_esplora_fee_estimates_is_target_rate_map(node):
    drv = _Capture(node)
    status, body = drv.get("/esplora/fee-estimates")
    assert status == 200
    fees = json.loads(body)
    assert "1" in fees and "6" in fees
    assert all(isinstance(v, (int, float)) and v >= 1 for v in fees.values())


def test_esplora_404s(node):
    drv = _Capture(node)
    assert drv.get("/esplora/tx/" + "0" * 64)[0] == 404
    assert drv.get("/esplora/block/deadbeef")[0] == 404
    assert drv.get("/esplora/block-height/999999")[0] == 404
    assert drv.get("/esplora/nonsense")[0] == 404
