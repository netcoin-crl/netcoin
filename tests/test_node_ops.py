"""Node ops: propagation event log, rate limiting, timeout/retry config, and
multi-node mempool/block propagation."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from netcoin.chain import Blockchain
from netcoin.miner import solve_template
from netcoin.node import NetCoinNode, RateLimiter, client_ip_from_headers, make_handler
from netcoin.tx import amount_to_sats
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


def clone(tmp_path: Path, name: str, source: Blockchain) -> Blockchain:
    c = Blockchain(tmp_path / name)
    for block in source.chain[1:]:
        c.add_block(block)
    return c


def test_rate_limiter_unit():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    assert rl.allow("other") is True  # different key independent
    assert RateLimiter(max_requests=0).allow("k") is True  # 0 = disabled


def test_client_ip_ignores_forwarded_header_unless_trusted():
    headers = {"X-Forwarded-For": "203.0.113.9, 198.51.100.7"}
    client_address = ("127.0.0.1", 12345)
    assert client_ip_from_headers(headers, client_address) == "127.0.0.1"
    assert client_ip_from_headers(headers, client_address, trust_proxy_headers=True) == "203.0.113.9"


def test_accept_block_logs_propagation_events(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    node = NetCoinNode(chain, persist=False)
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)

    node.accept_block(block)
    kinds = [e["event"] for e in node.recent_events()]
    assert "block_received" in kinds
    assert "block_accepted" in kinds


def test_events_endpoint_over_http(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)
    with served(NetCoinNode(chain, persist=False)) as s:
        req = Request(f"{s.url}/block", data=json.dumps(block.to_dict()).encode(), headers={"Content-Type": "application/json"}, method="POST")
        urlopen(req, timeout=5).read()
        with urlopen(f"{s.url}/events", timeout=5) as r:
            events = json.loads(r.read().decode())["events"]
    assert any(e["event"] == "block_accepted" for e in events)


def test_relay_endpoint_reports_queue(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "chain"), peers=["http://127.0.0.1:1"], persist=False)
    node.enqueue_relay("tx", "/tx", "abc", {"version": 1})
    with served(node) as s:
        with urlopen(f"{s.url}/relay", timeout=5) as r:
            data = json.loads(r.read().decode())
    assert data["queue"] == 1
    assert data["items"][0]["kind"] == "tx"


def test_post_endpoint_rate_limited(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain, persist=False, rate_limit_per_min=2)
    with served(node) as s:
        codes = []
        for _ in range(3):
            req = Request(f"{s.url}/tx", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            try:
                urlopen(req, timeout=5).read()
                codes.append(200)
            except HTTPError as exc:
                codes.append(exc.code)
    # First two pass the limiter (then fail validation as 400); third is 429.
    assert codes[2] == 429
    assert codes[0] in (200, 400) and codes[1] in (200, 400)


def test_get_endpoint_rate_limited(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain, persist=False, rate_limit_per_min=2)
    with served(node) as s:
        codes = []
        for _ in range(3):
            try:
                urlopen(f"{s.url}/info", timeout=5).read()
                codes.append(200)
            except HTTPError as exc:
                codes.append(exc.code)
    assert codes == [200, 200, 429]


def test_get_rate_limit_cannot_be_bypassed_with_spoofed_forwarded_for(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain, persist=False, rate_limit_per_min=1)
    with served(node) as s:
        first = Request(f"{s.url}/info", headers={"X-Forwarded-For": "203.0.113.1"})
        second = Request(f"{s.url}/info", headers={"X-Forwarded-For": "203.0.113.2"})
        with urlopen(first, timeout=5) as response:
            assert response.status == 200
        with pytest.raises(HTTPError) as excinfo:
            urlopen(second, timeout=5)
        assert excinfo.value.code == 429


def test_request_retry_and_timeout_are_configurable(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "chain"), persist=False, request_retries=3, request_timeout=2)
    assert node.request_retries == 3
    assert node.request_timeout == 2
    # A dead peer still raises (after retries) without hanging.
    with pytest.raises(Exception):
        node.fetch_json("http://127.0.0.1:1/info", timeout=1)


def test_mempool_transaction_propagates_to_peer(tmp_path: Path):
    miner = Wallet.create()
    receiver = Wallet.create()
    chain_a = Blockchain(tmp_path / "a")
    for _ in range(101):
        chain_a.mine_block(miner.address)
    chain_b = clone(tmp_path, "b", chain_a)  # same UTXO set

    with served(NetCoinNode(chain_b, persist=False)) as s:
        node_a = NetCoinNode(chain_a, peers=[s.url], persist=False)
        tx = miner.create_transaction(chain_a, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
        chain_a.add_mempool_transaction(tx)
        delivered = node_a.broadcast_transaction(tx)

    assert delivered == 1
    assert tx.txid() in {e["txid"] for e in chain_b.mempool_info()["entries"]}
