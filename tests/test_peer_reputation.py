"""Peer banning, scoring, and protocol-version negotiation (#1, #2, #18)."""
import time
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


def test_trusted_peer_is_never_auto_banned(tmp_path: Path):
    """A configured --peer must survive a long run of transient failures."""
    trusted = "http://seed2.example:28444"
    node = make_node(tmp_path, peers=[trusted], ban_threshold=-5)
    for _ in range(20):
        node.score_peer(trusted, -1, reason="sync failure")
    assert node.is_banned(trusted) is False
    assert trusted in node.peers
    # An explicit ban call is also refused for a trusted peer.
    node.ban_peer(trusted, reason="manual")
    assert node.is_banned(trusted) is False


def test_trusted_peer_auto_unbanned_on_restart(tmp_path: Path):
    """A stale ban on a configured seed is cleared when the node restarts."""
    import json
    seed = "http://seed3.example:28444"
    # Simulate a previous run that banned the seed (e.g. during a deploy blip).
    node = make_node(tmp_path, name="seednode")
    (node.banned_path).write_text(json.dumps({"banned": [seed]}))
    # Restart WITH the seed configured as --peer -> it should be unbanned + re-added.
    restarted = NetCoinNode(Blockchain(tmp_path / "seednode"), peers=[seed])
    assert restarted.is_banned(seed) is False
    assert seed in restarted.peers


def test_untrusted_ban_expires_after_ttl(tmp_path: Path):
    seed = "http://attacker.example:28444"
    node = make_node(tmp_path, ban_ttl_seconds=1)
    node.ban_peer(seed, reason="bad block")
    assert node.is_banned(seed) is True
    # Backdate the ban beyond the TTL; the next check should expire it.
    node.ban_times[seed] = time.time() - 5
    assert node.is_banned(seed) is False
    assert seed not in node.banned


def test_permanent_ban_when_ttl_zero(tmp_path: Path):
    seed = "http://attacker.example:28444"
    node = make_node(tmp_path, ban_ttl_seconds=0)
    node.ban_peer(seed)
    node.ban_times[seed] = time.time() - 10_000
    assert node.is_banned(seed) is True  # ttl=0 -> permanent
