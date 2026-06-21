"""HTTP peer-to-peer node for NetCoin.

The transport is intentionally simple JSON over HTTP, but the exposed concepts are
Bitcoin-like: peer discovery, headers-first sync shape, block/transaction relay,
compact block summaries, mempool exchange, block templates, and orphan handling.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .block import Block
from .chain import Blockchain
from .compact import CompactBlock, make_compact_block, reconstruct_compact_block
from .params import DEFAULT_NODE_PORT, PROTOCOL_VERSION
from .tx import Transaction


class NodeError(ValueError):
    """Raised when node-level operations fail."""


class NetCoinNode:
    def __init__(self, chain: Blockchain, peers: Optional[Iterable[str]] = None):
        self.chain = chain
        self.peers = set()
        self.orphans: Dict[str, Block] = {}
        for peer in peers or []:
            self.add_peer(peer)

    def add_peer(self, peer: str) -> None:
        peer = peer.rstrip("/")
        if not peer.startswith(("http://", "https://")):
            raise NodeError("peer must start with http:// or https://")
        self.peers.add(peer)

    def info(self) -> Dict[str, Any]:
        data = self.chain.chain_info()
        data.update(
            {
                "protocol_version": PROTOCOL_VERSION,
                "peers": sorted(self.peers),
                "orphans": len(self.orphans),
                "services": ["network", "headers", "compact-blocks", "mempool", "block-template"],
            }
        )
        return data

    def fetch_json(self, url: str, timeout: int = 5) -> Dict[str, Any]:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, url: str, payload: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def sync_from_peer(self, peer: str) -> bool:
        peer = peer.rstrip("/")
        try:
            remote = self.fetch_json(f"{peer}/info").get("node", {})
            if int(remote.get("height", 0)) <= self.chain.height():
                return False
            # Headers-first shape: inspect remote headers before full block download.
            self.fetch_json(f"{peer}/headers?start=0&limit=5000")
        except Exception:
            pass
        data = self.fetch_json(f"{peer}/chain")
        blocks = self.chain.import_chain_data(data)
        return self.chain.replace_chain(blocks)

    def sync_all(self) -> int:
        adopted = 0
        for peer in list(self.peers):
            try:
                if self.sync_from_peer(peer):
                    adopted += 1
            except Exception:
                continue
        return adopted

    def accept_block(self, block: Block) -> str:
        try:
            block_hash = self.chain.add_block(block)
        except Exception:
            self.orphans[block.hash()] = block
            self.sync_all()
            raise
        progressed = True
        while progressed:
            progressed = False
            for orphan_hash, orphan in list(self.orphans.items()):
                if orphan.header.previous_hash == self.chain.tip_hash():
                    try:
                        self.chain.add_block(orphan)
                        del self.orphans[orphan_hash]
                        progressed = True
                    except Exception:
                        pass
        return block_hash

    def broadcast_transaction(self, tx: Transaction) -> int:
        payload = tx.to_dict(include_scripts=True, include_witness=True)
        delivered = 0
        for peer in list(self.peers):
            try:
                self.post_json(f"{peer}/tx", payload)
                delivered += 1
            except Exception:
                continue
        return delivered

    def broadcast_block(self, block: Block) -> int:
        payload = block.to_dict()
        delivered = 0
        for peer in list(self.peers):
            try:
                self.post_json(f"{peer}/block", payload)
                delivered += 1
            except Exception:
                continue
        return delivered


def make_handler(node: NetCoinNode):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NetCoinNode/0.2"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib method name
            return

        def read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_error_json(self, message: str, status: int = 400) -> None:
            self.send_json({"ok": False, "error": message}, status=status)

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            try:
                if parsed.path in ("/", "/info"):
                    self.send_json({"ok": True, "node": node.info()})
                elif parsed.path == "/chain":
                    self.send_json(node.chain.export_chain())
                elif parsed.path == "/headers":
                    query = parse_qs(parsed.query)
                    start = int(query.get("start", [0])[0])
                    limit = int(query.get("limit", [2000])[0])
                    self.send_json({"headers": node.chain.header_list(start, limit)})
                elif parsed.path.startswith("/block/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        self.send_json(block.to_dict() | {"hash": block.hash(), "weight": block.weight()})
                elif parsed.path.startswith("/compact-block/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        self.send_json(make_compact_block(block).to_dict())
                elif parsed.path == "/blocktemplate":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [None])[0]
                    self.send_json(node.chain.get_block_template(miner_address=address))
                elif parsed.path == "/mempool":
                    self.send_json(node.chain.export_mempool())
                elif parsed.path == "/peers":
                    self.send_json({"peers": sorted(node.peers)})
                elif parsed.path == "/utxos":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [""])[0]
                    utxos = [utxo.to_dict() for utxo in node.chain.utxos_for_address(address)]
                    self.send_json({"address": address, "utxos": utxos})
                else:
                    self.send_error_json("not found", status=404)
            except Exception as exc:
                self.send_error_json(str(exc), status=400)

        def do_POST(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            try:
                data = self.read_json()
                if parsed.path == "/tx":
                    tx = Transaction.from_dict(data)
                    txid = node.chain.add_mempool_transaction(tx)
                    delivered = node.broadcast_transaction(tx)
                    self.send_json({"ok": True, "txid": txid, "relayed_to": delivered})
                elif parsed.path in ("/block", "/submitblock"):
                    block = Block.from_dict(data)
                    block_hash = node.accept_block(block)
                    delivered = node.broadcast_block(block)
                    self.send_json({"ok": True, "block_hash": block_hash, "relayed_to": delivered})
                elif parsed.path == "/compact-block":
                    compact = CompactBlock.from_dict(data)
                    block = reconstruct_compact_block(compact, node.chain.mempool)
                    block_hash = node.accept_block(block)
                    delivered = node.broadcast_block(block)
                    self.send_json({"ok": True, "block_hash": block_hash, "relayed_to": delivered})
                elif parsed.path == "/peers":
                    for peer in data.get("peers", []):
                        node.add_peer(str(peer))
                    self.send_json({"ok": True, "peers": sorted(node.peers)})
                elif parsed.path == "/sync":
                    adopted = node.sync_all()
                    self.send_json({"ok": True, "adopted_chains": adopted, "info": node.info()})
                else:
                    self.send_error_json("not found", status=404)
            except Exception as exc:
                self.send_error_json(str(exc), status=400)

    return Handler


def run_node(data_dir: str, host: str = "127.0.0.1", port: int = DEFAULT_NODE_PORT, peers: Optional[List[str]] = None) -> None:
    chain = Blockchain(data_dir=data_dir)
    node = NetCoinNode(chain, peers=peers or [])
    node.sync_all()
    server = ThreadingHTTPServer((host, port), make_handler(node))
    print(f"NetCoin node listening on http://{host}:{port}")
    print(f"height={chain.height()} tip={chain.tip_hash()}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
