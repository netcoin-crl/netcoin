from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from netcoin.chain import Blockchain
from netcoin.cli import normalize_advertise_url
from netcoin.node import NetCoinNode, make_handler


def _node(tmp_path: Path, *, self_url: str | None = None) -> NetCoinNode:
    return NetCoinNode(Blockchain(tmp_path / "chain"), peers=[], self_url=self_url, persist=False, request_retries=0)


def test_announce_self_surfaces_unreachable_advertise_but_still_announces(tmp_path: Path, monkeypatch):
    # Advisory, not blocking: many home routers don't support NAT hairpinning,
    # so a node can legitimately fail to dial its own forwarded public address
    # from inside its own LAN even though outside peers reach it fine. Gating
    # announce_self() on this self-check would silently stop exactly the
    # correctly-configured home seeds it's meant to help -- so a failed
    # self-check is surfaced in /info for operator visibility, but gossip
    # still goes out. normalize_advertise_url (cli.py) is the real defense
    # against placeholder/private-range addresses.
    node = _node(tmp_path, self_url="http://198.51.100.7:28444")
    node.add_peer("http://seed.example:28444")
    posted = []

    def fake_fetch(url: str):
        assert url == "http://198.51.100.7:28444/peers/echo-addr"
        raise OSError("cannot dial self")

    monkeypatch.setattr(node, "fetch_json", fake_fetch)
    monkeypatch.setattr(node, "post_json", lambda url, payload: posted.append((url, payload)))

    assert node.announce_self() == 1
    assert posted == [("http://seed.example:28444/peers", {"peers": ["http://198.51.100.7:28444"]})]
    info = node.info()
    assert info["advertise"] == "http://198.51.100.7:28444"
    assert info["advertise_unreachable"] is True
    assert "cannot dial self" in info["advertise_unreachable_error"]


def test_announce_self_dials_own_url_once_before_gossiping(tmp_path: Path, monkeypatch):
    node = _node(tmp_path, self_url="http://198.51.100.8:28444")
    node.add_peer("http://seed.example:28444")
    fetched = []
    posted = []

    def fake_fetch(url: str):
        fetched.append(url)
        return {"ok": True, "observed_ip": "198.51.100.8"}

    monkeypatch.setattr(node, "fetch_json", fake_fetch)
    monkeypatch.setattr(node, "post_json", lambda url, payload: posted.append((url, payload)))

    assert node.announce_self() == 1
    assert node.announce_self() == 1
    assert fetched == ["http://198.51.100.8:28444/peers/echo-addr"]
    assert posted == [
        ("http://seed.example:28444/peers", {"peers": ["http://198.51.100.8:28444"]}),
        ("http://seed.example:28444/peers", {"peers": ["http://198.51.100.8:28444"]}),
    ]
    assert node.info()["advertise_unreachable"] is False


def test_peers_echo_addr_returns_observed_client_ip(tmp_path: Path):
    node = _node(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        payload = json.loads(urlopen(base + "/peers/echo-addr").read())
    finally:
        server.shutdown()

    assert payload == {"ok": True, "observed_ip": "127.0.0.1"}


@pytest.mark.parametrize(
    "advertise",
    [
        "10.0.0.5:28444",
        "172.16.1.5:28444",
        "172.31.1.5:28444",
        "192.168.1.10:28444",
        "127.0.0.1:28444",
        "localhost:28444",
        "203.0.113.5:28444",
        "169.254.1.5:28444",
        "[::1]:28444",
        "[fe80::1]:28444",
        "[fc00::1]:28444",
    ],
)
def test_normalize_advertise_url_rejects_unreachable_example_ranges(advertise: str):
    with pytest.raises(ValueError, match="public"):
        normalize_advertise_url(advertise)


def test_normalize_advertise_url_allows_public_dns_and_adds_scheme():
    assert normalize_advertise_url("seed.netcoin.example:28444") == "http://seed.netcoin.example:28444"
