from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.chain import Blockchain
from netcoin.rpc import RPCServer, make_handler
from netcoin.wallet import Wallet


def _post_json(base: str, payload):
    req = Request(
        base,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_rpc_bitcoin_style_method_matrix(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    rpc = RPCServer(chain)

    assert rpc.call("getblockcount", []) == chain.height()
    assert rpc.call("getbestblockhash", []) == chain.tip_hash()
    info = rpc.call("getblockchaininfo", [])
    assert info["height"] == chain.height()
    assert info["blocks"] == len(chain.chain)
    network = rpc.call("getnetworkinfo", [])
    assert network["protocolversion"] > 0
    assert network["networkactive"] is True
    assert rpc.call("getrawmempool", []) == []
    assert rpc.call("estimatesmartfee", [2])["blocks"] == 2
    assert rpc.call("validateaddress", [miner.address])["isvalid"] is True


def test_rpc_http_supports_batch_requests_and_preserves_ids(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    rpc = RPCServer(chain)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(rpc))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status, payload = _post_json(
            base,
            [
                {"jsonrpc": "2.0", "id": "height", "method": "getblockcount", "params": []},
                {"jsonrpc": "2.0", "id": "tip", "method": "getbestblockhash"},
            ],
        )
    finally:
        server.shutdown()

    assert status == 200
    assert [item["id"] for item in payload] == ["height", "tip"]
    assert payload[0]["result"] == chain.height()
    assert payload[1]["result"] == chain.tip_hash()
    assert all(item["error"] is None for item in payload)


def test_rpc_http_error_preserves_request_id(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    rpc = RPCServer(chain)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(rpc))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status, payload = _post_json(
            base,
            {"jsonrpc": "2.0", "id": "client-123", "method": "notamethod", "params": []},
        )
    finally:
        server.shutdown()

    assert status == 400
    assert payload["id"] == "client-123"
    assert payload["result"] is None
    assert "unknown RPC method" in payload["error"]
