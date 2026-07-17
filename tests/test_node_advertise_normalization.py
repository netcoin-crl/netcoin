"""Advertising a bare host:port (what the wallet's Seed tab collects) must not
crash the node.

Peers are dialed as http:// URLs, and NetCoinNode._normalize_peer rejects a
bare host:port. The Seed tab documents/collects advertise as host:port (its
placeholder used a documentation-range address), so without normalization the
node refused to start with "peer must start with http:// or https://". This
pins the fix: cmd_node prepends http:// to a scheme-less advertise.
"""

import argparse
import tempfile

import netcoin.cli as cli
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode


def _node_args(advertise):
    return argparse.Namespace(
        data=tempfile.mkdtemp(),
        host="127.0.0.1",
        port=28444,
        advertise=advertise,
        seeds=False,
        sync_interval=0,
        rate_limit_per_min=240,
        trust_proxy_headers=False,
        bandwidth_mode=None,
        peer=[],
        config=None,
        p2p_port=0,
    )


def test_bare_hostport_advertise_is_normalized_to_a_url(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "run_node", lambda **kwargs: captured.update(kwargs))
    cli.cmd_node(_node_args("198.51.100.10:28444"))
    assert captured["advertise"] == "http://198.51.100.10:28444"


def test_url_advertise_is_left_unchanged(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "run_node", lambda **kwargs: captured.update(kwargs))
    cli.cmd_node(_node_args("http://seed9.netcoin.online:28444"))
    assert captured["advertise"] == "http://seed9.netcoin.online:28444"


def test_blank_advertise_stays_none(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "run_node", lambda **kwargs: captured.update(kwargs))
    cli.cmd_node(_node_args(None))
    assert captured["advertise"] is None


def test_node_accepts_the_normalized_url_form(tmp_path):
    # The whole point of the normalization: the URL form must actually construct.
    node = NetCoinNode(Blockchain(tmp_path / "chain"), self_url="http://198.51.100.10:28444")
    assert node.self_url == "http://198.51.100.10:28444"
