"""Block propagation: relay de-duplication so echoed blocks do not loop."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from netcoin.chain import Blockchain
from netcoin.miner import solve_template
from netcoin.node import NetCoinNode
from netcoin.wallet import Wallet


def counting_peer():
    counts = {"block": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            if self.path == "/block":
                counts["block"] += 1
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_address[1]}", counts


def test_broadcast_block_is_deduplicated(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)

    server, thread, url, counts = counting_peer()
    node = NetCoinNode(chain, peers=[url], persist=False)
    try:
        # First relay reaches the peer.
        assert node.broadcast_block(block) == 1
        assert counts["block"] == 1
        # An echo of the same block is suppressed.
        assert node.broadcast_block(block) == 0
        assert counts["block"] == 1
        # force=True re-sends (e.g. an operator-triggered rebroadcast).
        assert node.broadcast_block(block, force=True) == 1
        assert counts["block"] == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_relay_new_blocks_relays_received_block(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)

    server, thread, url, counts = counting_peer()
    node = NetCoinNode(chain, peers=[url], persist=False)
    try:
        node.accept_block(block)
        delivered = node.relay_new_blocks(block)
        assert delivered == 1
        assert counts["block"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
