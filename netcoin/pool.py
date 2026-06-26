"""Tiny educational mining-pool server for NetCoin.

This is not Stratum-compatible production pool software. It exposes a simple HTTP
job/template API so several local miners can request block templates and submit
whole solved blocks.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .block import Block
from .chain import Blockchain
from .params import DEFAULT_POOL_PORT, MAX_REQUEST_BODY_BYTES


class MiningPool:
    def __init__(self, chain: Blockchain, payout_address: str):
        self.chain = chain
        self.payout_address = payout_address
        self.accepted = 0
        self.rejected = 0

    def job(self) -> Dict[str, Any]:
        template = self.chain.get_block_template(miner_address=self.payout_address)
        template["pool"] = {"payout_address": self.payout_address, "accepted": self.accepted, "rejected": self.rejected}
        return template

    def submit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        block = Block.from_dict(data["block"])
        try:
            block_hash = self.chain.add_block(block)
            self.accepted += 1
            return {"ok": True, "block_hash": block_hash, "height": block.header.height}
        except Exception as exc:
            self.rejected += 1
            return {"ok": False, "error": str(exc)}


class PoolError(ValueError):
    pass


def make_handler(pool: MiningPool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NetCoinPool/0.2"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self) -> Dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError) as exc:
                raise PoolError("invalid Content-Length") from exc
            if length > MAX_REQUEST_BODY_BYTES:
                raise PoolError("request body too large")
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/job", "/getblocktemplate"):
                self.send_json(pool.job())
            else:
                self.send_json({"ok": False, "error": "not found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            try:
                if self.path == "/submit":
                    self.send_json(pool.submit(self.read_json()))
                else:
                    self.send_json({"ok": False, "error": "not found"}, status=404)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)

    return Handler


def run_pool(data_dir: str, payout_address: str, host: str = "127.0.0.1", port: int = DEFAULT_POOL_PORT) -> None:
    chain = Blockchain(data_dir=data_dir)
    pool = MiningPool(chain, payout_address=payout_address)
    server = ThreadingHTTPServer((host, port), make_handler(pool))
    print(f"NetCoin educational pool listening on http://{host}:{port}")
    print(f"payout_address={payout_address}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
