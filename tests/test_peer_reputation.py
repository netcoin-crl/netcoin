"""Peer banning, scoring, and protocol-version negotiation (#1, #2, #18)."""
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode
from netcoin.params import NETWORK_NAME, PROTOCOL_VERSION


def make_node(tmp_path: Path, name="n", **kw) -> NetCoinNode:
    return NetCoinNode(Blockchain(tmp_path / name), **kw)


def test_ban_and_unban_persist(tmp_path: Path):
    node = make_node(tmp_path)
    node.ban_peer("http://bad.example:28444", reason="invalid block")
    assert node.is_banned("http://bad.example:28444") is True
    assert "http://bad.example:28444" in node.banned

    # A fresh node on the same data dir reloads the ban list.
    reloaded = NetCoinNode(Blockchain(tmp_path / "n"))
    assert reloaded.is_banned("http://bad.example:28444") is True
    assert reloaded.unban_peer("http://bad.example:28444") is True
    assert NetCoinNode(Blockchain(tmp_path / "n")).is_banned("http://bad.example:28444") is False


def test_add_peer_refuses_banned(tmp_path: Path):
    node = make_node(tmp_path)
    node.ban_peer("http://bad.example:28444")
    node.add_peer("http://bad.example:28444")
    assert "http://bad.example:28444" not in node.peers


def test_score_auto_bans_at_threshold(tmp_path: Path):
    node = make_node(tmp_path, ban_threshold=-3)
    peer = "http://flaky.example:28444"
    node.add_peer(peer)
    assert node.score_peer(peer, -1) == -1
    assert node.score_peer(peer, -1) == -2
    assert not node.is_banned(peer)
    node.score_peer(peer, -1)  # hits -3
    assert node.is_banned(peer)
    assert peer not in node.peers


def test_compatible_peer_protocol_version(tmp_path: Path):
    node = make_node(tmp_path)
    base = {"genesis_hash": node.genesis_hash(), "network": NETWORK_NAME}
    assert node.compatible_peer({**base, "protocol_version": PROTOCOL_VERSION}) is True
    assert node.compatible_peer({**base, "protocol_version": PROTOCOL_VERSION + 1}) is False
    assert node.compatible_peer(base) is True  # missing protocol is tolerated


def test_sync_all_scores_dead_peer_negative(tmp_path: Path):
    node = make_node(tmp_path, peers=["http://127.0.0.1:1"], persist=False)
    node.sync_all()
    assert node.peer_scores.get("http://127.0.0.1:1", 0) < 0
