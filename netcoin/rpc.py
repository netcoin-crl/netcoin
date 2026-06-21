"""Small JSON-RPC server for NetCoin."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .chain import Blockchain
from .params import DEFAULT_RPC_PORT, TICKER
from .block import Block
from .serialization import block_to_raw_hex, decode_raw_transaction, tx_to_raw_hex
from .tx import Transaction, sats_to_amount


class RPCError(ValueError):
    pass


class RPCServer:
    def __init__(self, chain: Blockchain):
        self.chain = chain

    def call(self, method: str, params: list[Any]) -> Any:
        if method == "getblockchaininfo":
            return self.chain.chain_info()
        if method == "getblockcount":
            return self.chain.height()
        if method == "getbestblockhash":
            return self.chain.tip_hash()
        if method == "getrawmempool":
            verbose = bool(params[0]) if params else False
            if not verbose:
                return [tx.txid() for tx in self.chain.mempool]
            fees = self.chain.fee_lookup()
            return {
                tx.txid(): {"vsize": tx.vsize(), "weight": tx.weight(), "fee": fees.get(tx.txid(), 0)}
                for tx in self.chain.mempool
            }
        if method == "getblock":
            block_hash = str(params[0]) if params else self.chain.tip_hash()
            verbosity = int(params[1]) if len(params) > 1 else 1
            block = self.chain.block_by_hash(block_hash)
            if block is None:
                raise RPCError("block not found")
            if verbosity == 0:
                return block_to_raw_hex(block)
            data = block.to_dict()
            data["hash"] = block.hash()
            data["weight"] = block.weight()
            return data
        if method == "getblockheader":
            block_hash = str(params[0]) if params else self.chain.tip_hash()
            block = self.chain.block_by_hash(block_hash)
            if block is None:
                raise RPCError("block not found")
            return block.header.to_dict() | {"hash": block.hash()}
        if method == "getrawtransaction":
            txid = str(params[0])
            verbose = bool(params[1]) if len(params) > 1 else False
            tx = self.find_tx(txid)
            if tx is None:
                raise RPCError("transaction not found")
            raw = tx_to_raw_hex(tx)
            if not verbose:
                return raw
            decoded = decode_raw_transaction(raw)
            decoded.update({"txid": tx.txid(), "wtxid": tx.wtxid(), "weight": tx.weight(), "vsize": tx.vsize()})
            return decoded
        if method == "sendrawtransaction":
            data = params[0]
            if isinstance(data, dict):
                tx = Transaction.from_dict(data)
            else:
                raise RPCError("sendrawtransaction currently accepts NetCoin transaction JSON")
            return self.chain.add_mempool_transaction(tx)
        if method == "estimatesmartfee":
            target = int(params[0]) if params else 1
            sat_vb = self.chain.estimate_fee_rate(target)
            return {"feerate_sat_vb": sat_vb, "feerate_net_kvb": sats_to_amount(sat_vb * 1000), "blocks": target}
        if method == "getblocktemplate":
            address = str(params[0]) if params else None
            return self.chain.get_block_template(miner_address=address)
        if method == "submitblock":
            if not params:
                raise RPCError("submitblock requires a block JSON object")
            block = Block.from_dict(params[0])
            return self.chain.add_block(block)
        if method == "validatechain":
            self.chain.assert_valid_chain(self.chain.chain)
            return True
        raise RPCError(f"unknown RPC method: {method}")

    def find_tx(self, txid: str) -> Optional[Transaction]:
        for tx in self.chain.mempool:
            if tx.txid() == txid:
                return tx
        for block in self.chain.chain:
            for tx in block.transactions:
                if tx.txid() == txid:
                    return tx
        return None


def make_handler(rpc: RPCServer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NetCoinRPC/0.2"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                result = rpc.call(str(request.get("method")), list(request.get("params", [])))
                payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": result, "error": None}
                self.send_json(payload)
            except Exception as exc:
                self.send_json({"jsonrpc": "2.0", "id": None, "result": None, "error": str(exc)}, status=400)

        def do_GET(self) -> None:  # noqa: N802
            self.send_json({"ok": True, "service": "NetCoin JSON-RPC", "methods": RPC_METHODS})

        def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


RPC_METHODS = [
    "getblockchaininfo",
    "getblockcount",
    "getbestblockhash",
    "getrawmempool",
    "getblock",
    "getblockheader",
    "getrawtransaction",
    "sendrawtransaction",
    "estimatesmartfee",
    "getblocktemplate",
    "submitblock",
    "validatechain",
]


def run_rpc(data_dir: str, host: str = "127.0.0.1", port: int = DEFAULT_RPC_PORT) -> None:
    chain = Blockchain(data_dir=data_dir)
    rpc = RPCServer(chain)
    server = ThreadingHTTPServer((host, port), make_handler(rpc))
    print(f"NetCoin RPC listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
