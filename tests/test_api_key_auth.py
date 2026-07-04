"""NIP-0004 write auth: self-service API keys + node-level write enforcement."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
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


def post(url, payload, headers=None):
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urlopen(req, timeout=5) as res:
        return res.status, json.loads(res.read().decode())


def test_self_service_key_register_verify_and_ip_cap(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)

    first = store.register_public_api_key({"app": "demo"}, "203.0.113.9")
    assert first["api_key"].startswith("nck_")
    assert store.check_api_key(first["api_key"]) is True
    assert store.check_api_key("nck_wrong") is False
    assert store.check_api_key("") is False

    for _ in range(9):
        store.register_public_api_key({}, "203.0.113.9")
    with pytest.raises(AppError, match="registration limit"):
        store.register_public_api_key({}, "203.0.113.9")
    # A different IP is unaffected.
    assert store.register_public_api_key({}, "203.0.113.10")["api_key"]


def test_node_enforces_api_key_on_writes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NETCOIN_APP_REQUIRE_API_KEY", "1")
    chain = Blockchain(tmp_path / "chain")
    alice = Wallet.create()
    chain.mine_block(alice.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        # Registration itself must stay open.
        status, reg = post(f"{s.url}/api/keys/register", {"app": "test"})
        assert status == 200 and reg["api_key"].startswith("nck_")

        # Write without a key -> 401 with a self-help message.
        with pytest.raises(HTTPError) as err:
            post(f"{s.url}/api/tokens", {"symbol": "AUTH", "creator": alice.segwit_address, "initial_supply": "1", "decimals": 0})
        assert err.value.code == 401
        assert "keys/register" in err.value.read().decode()

        # Same write with the key -> accepted.
        status, created = post(
            f"{s.url}/api/tokens",
            {"symbol": "AUTH", "creator": alice.segwit_address, "initial_supply": "1", "decimals": 0},
            headers={"X-Netcoin-Api-Key": reg["api_key"]},
        )
        assert status == 200 and created["symbol"] == "AUTH"

        # Community posts remain public (existing carve-out).
        status, _ = post(f"{s.url}/api/community/posts", {"author": "anon", "message": "hello world"})
        assert status == 200


def test_enforcement_off_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("NETCOIN_APP_REQUIRE_API_KEY", raising=False)
    chain = Blockchain(tmp_path / "chain")
    alice = Wallet.create()
    chain.mine_block(alice.address)
    with served(NetCoinNode(chain, persist=False)) as s:
        status, created = post(f"{s.url}/api/tokens", {"symbol": "OPEN", "creator": alice.segwit_address, "initial_supply": "1", "decimals": 0})
        assert status == 200 and created["symbol"] == "OPEN"
