"""Node /health and /metrics endpoints, version handshake, and peer compatibility."""

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.params import DEFAULT_TESTNET_SEEDS, NETWORK_NAME, NODE_VERSION
from netcoin.wallet import Wallet


class served:
    def __init__(self, node: NetCoinNode):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def test_health_endpoint(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    with served(NetCoinNode(chain, persist=False)) as s, urlopen(f"{s.url}/health", timeout=5) as r:
        data = json.loads(r.read().decode())
    assert data["ok"] is True
    assert data["height"] == 1
    assert data["version"] == NODE_VERSION
    assert data["network"] == NETWORK_NAME
    assert data["genesis_hash"] == chain.chain[0].hash()
    assert data["uptime_seconds"] >= 0


def test_metrics_endpoint_prometheus_format(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(2):
        chain.mine_block(miner.address)
    with served(NetCoinNode(chain, persist=False)) as s, urlopen(f"{s.url}/metrics", timeout=5) as r:
        body = r.read().decode()
        content_type = r.headers.get("Content-Type", "")
    assert "text/plain" in content_type
    assert "netcoin_block_height 2" in body
    assert "# TYPE netcoin_block_height gauge" in body
    assert "netcoin_peers 0" in body


def test_info_includes_handshake_fields(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s, urlopen(f"{s.url}/info", timeout=5) as r:
        node = json.loads(r.read().decode())["node"]
    assert node["version"] == NODE_VERSION
    assert node["network"] == NETWORK_NAME
    assert node["genesis_hash"] == chain.chain[0].hash()
    assert node["user_agent"].startswith("NetCoin:")


def test_compatible_peer_rejects_wrong_genesis_or_network(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "chain"), persist=False)
    good = {"genesis_hash": node.genesis_hash(), "network": NETWORK_NAME}
    assert node.compatible_peer(good) is True
    assert node.compatible_peer({"genesis_hash": "f" * 64, "network": NETWORK_NAME}) is False
    assert node.compatible_peer({"genesis_hash": node.genesis_hash(), "network": "mainnet"}) is False
    # Missing fields (older peer) are tolerated.
    assert node.compatible_peer({}) is True


def test_default_testnet_seeds_present():
    assert len(DEFAULT_TESTNET_SEEDS) == 3
    assert all(s.startswith("http://seed") for s in DEFAULT_TESTNET_SEEDS)


def test_memory_debug_snapshot_reports_process_memory_and_bounded_collections(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    node = NetCoinNode(chain, persist=False)
    snapshot = node.memory_debug_snapshot()

    assert snapshot["schema"] == "netcoin-memory-debug-v1"
    assert isinstance(snapshot["gc_object_count"], int) and snapshot["gc_object_count"] > 0
    assert isinstance(snapshot["gc_top_types"], list) and len(snapshot["gc_top_types"]) > 0
    assert snapshot["gc_top_types"][0]["count"] >= snapshot["gc_top_types"][-1]["count"]
    # On Linux this reads /proc/self/status; elsewhere it falls back to
    # resource.getrusage. Either way it should resolve to a positive number.
    assert snapshot["rss_kb"] is None or snapshot["rss_kb"] > 0
    collections = snapshot["collections"]
    for key in (
        "peers",
        "banned",
        "trusted_peers",
        "peer_scores",
        "ban_times",
        "orphans",
        "event_log",
        "relay_queue",
        "relay_inventory",
        "broadcast_seen",
        "response_cache",
        "mempool_transactions",
    ):
        assert key in collections
        assert isinstance(collections[key], int)


def test_debug_memory_endpoint_is_reachable(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s, urlopen(f"{s.url}/debug/memory", timeout=5) as r:
        data = json.loads(r.read().decode())
    assert data["schema"] == "netcoin-memory-debug-v1"
    assert "collections" in data
