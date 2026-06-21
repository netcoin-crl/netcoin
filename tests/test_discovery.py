"""Peer gossip / auto-discovery: pull peer lists, announce self, bounded growth."""
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import Wallet


class served:
    def __init__(self, node: NetCoinNode):
        self.node = node
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


def test_discover_peers_learns_from_peer(tmp_path: Path):
    remote = NetCoinNode(
        Blockchain(tmp_path / "b"),
        peers=["http://seedx.example:28444", "http://seedy.example:28444"],
        persist=False,
    )
    with served(remote) as s:
        local = NetCoinNode(Blockchain(tmp_path / "a"), peers=[s.url], persist=False)
        learned = local.discover_peers()

    assert "http://seedx.example:28444" in local.peers
    assert "http://seedy.example:28444" in local.peers
    assert learned >= 2


def test_announce_self_reaches_peer(tmp_path: Path):
    remote = NetCoinNode(Blockchain(tmp_path / "b"), persist=False)
    with served(remote) as s:
        local = NetCoinNode(
            Blockchain(tmp_path / "a"),
            peers=[s.url],
            persist=False,
            self_url="http://nodea.example:28444",
        )
        delivered = local.announce_self()
        assert delivered == 1
        # The remote node learned about us through the gossip push.
        assert "http://nodea.example:28444" in remote.peers


def test_discovery_excludes_self(tmp_path: Path):
    self_url = "http://nodea.example:28444"
    remote = NetCoinNode(
        Blockchain(tmp_path / "b"),
        peers=[self_url, "http://other.example:28444"],
        persist=False,
    )
    with served(remote) as s:
        local = NetCoinNode(Blockchain(tmp_path / "a"), peers=[s.url], persist=False, self_url=self_url)
        local.discover_peers()

    assert self_url not in local.peers
    assert "http://other.example:28444" in local.peers


def test_peer_cap_bounds_growth(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "a"), persist=False, max_peers=2)
    node.add_peer("http://p1.example:28444")
    node.add_peer("http://p2.example:28444")
    node.add_peer("http://p3.example:28444")
    assert len(node.peers) == 2


def test_bootstrap_learns_peers_and_syncs_chain(tmp_path: Path):
    miner = Wallet.create()
    remote_chain = Blockchain(tmp_path / "b")
    for _ in range(3):
        remote_chain.mine_block(miner.address)
    remote = NetCoinNode(remote_chain, peers=["http://seedx.example:28444"], persist=False)

    with served(remote) as s:
        local_chain = Blockchain(tmp_path / "a")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        result = local.bootstrap()

    assert local_chain.height() == 3
    assert local_chain.tip_hash() == remote_chain.tip_hash()
    assert "http://seedx.example:28444" in local.peers
    assert result["adopted_chains"] == 1
    assert result["learned"] >= 1
