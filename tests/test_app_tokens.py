"""App-layer NET-20 style token ledger tests (indexed ledger, not consensus)."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from netcoin.apps import AppError, AppStore, format_token_amount, parse_token_units, route_app_get, route_app_post
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


def get(url):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def make_store(tmp_path: Path) -> tuple[AppStore, Blockchain, Wallet, Wallet]:
    chain = Blockchain(tmp_path / "chain")
    alice = Wallet.create()
    bob = Wallet.create()
    chain.mine_block(alice.address)
    return AppStore(chain.data_dir), chain, alice, bob


def test_token_units_parsing_and_formatting():
    assert parse_token_units("1.5", 8) == 150_000_000
    assert parse_token_units(3, 2) == 300
    assert parse_token_units("0", 8, allow_zero=True) == 0
    assert format_token_amount(150_000_000, 8) == "1.50000000"
    assert format_token_amount(42, 0) == "42"
    with pytest.raises(AppError):
        parse_token_units("1.123", 2)
    with pytest.raises(AppError):
        parse_token_units("-1", 8)
    with pytest.raises(AppError):
        parse_token_units("0", 8)


def test_token_create_mint_transfer_burn(tmp_path: Path):
    store, _, alice, bob = make_store(tmp_path)

    token = store.create_token({"symbol": "demo", "name": "Demo Points", "decimals": 2, "creator": alice.segwit_address, "initial_supply": "100", "max_supply": "150"})
    assert token["symbol"] == "DEMO"
    assert token["standard"] == "NET-20"
    assert token["supply_units"] == 10_000

    # Symbol lookup works everywhere a token id works.
    assert store.token_info("demo")["token_id"] == token["token_id"]

    # Only the creator may mint, and max supply is enforced.
    with pytest.raises(AppError, match="only the token creator"):
        store.mint_token("DEMO", {"minter": bob.segwit_address, "amount": "1"})
    minted = store.mint_token("DEMO", {"minter": alice.segwit_address, "amount": "50"})
    assert minted["units"] == 15_000
    with pytest.raises(AppError, match="max supply"):
        store.mint_token("DEMO", {"minter": alice.segwit_address, "amount": "1"})

    # Transfers move balances and reject overdrafts.
    result = store.transfer_token("DEMO", {"from": alice.segwit_address, "to": bob.segwit_address, "amount": "25.5"})
    assert result["to"]["units"] == 2_550
    assert store.token_balance_of("DEMO", alice.segwit_address)["units"] == 12_450
    with pytest.raises(AppError, match="insufficient"):
        store.transfer_token("DEMO", {"from": bob.segwit_address, "to": alice.segwit_address, "amount": "1000"})

    # Burn reduces supply.
    store.burn_token("DEMO", {"from": bob.segwit_address, "amount": "0.5"})
    assert store.token_info("DEMO")["supply_units"] == 14_950

    holders = store.token_balances("DEMO")
    assert holders["holder_count"] == 2
    events = store.token_events("DEMO")["events"]
    assert [e["kind"] for e in events[:4]] == ["burn", "transfer", "mint", "create"]


def test_token_username_accounts_and_validation(tmp_path: Path):
    store, _, alice, _ = make_store(tmp_path)
    token = store.create_token({"symbol": "PTS", "creator": "@alice", "initial_supply": "10", "decimals": 0})
    assert token["balances"]["@alice"] == 10
    with pytest.raises(AppError):
        store.create_token({"symbol": "x", "creator": alice.segwit_address})  # bad symbol
    with pytest.raises(AppError, match="symbol already exists"):
        store.create_token({"symbol": "PTS", "creator": alice.segwit_address})
    with pytest.raises(AppError):
        store.transfer_token("PTS", {"from": "not-an-address", "to": "@alice", "amount": "1"})
    with pytest.raises(AppError, match="same account"):
        store.transfer_token("PTS", {"from": "@alice", "to": "@alice", "amount": "1"})


def test_token_http_routes(tmp_path: Path):
    store, chain, alice, bob = make_store(tmp_path)

    status, created = route_app_post(store, chain, "/api/tokens", {"symbol": "WEB", "creator": alice.segwit_address, "initial_supply": "5"})
    assert status == 200 and created["symbol"] == "WEB"

    status, _ = route_app_post(store, chain, f"/api/tokens/{created['token_id']}/transfer", {"from": alice.segwit_address, "to": bob.segwit_address, "amount": "2"})
    assert status == 200

    status, listing, ctype = route_app_get(store, chain, "/api/tokens", {})
    assert status == 200 and ctype == "application/json" and listing["count"] == 1

    status, info, _ = route_app_get(store, chain, "/api/tokens/WEB", {})
    assert info["holder_count"] == 2

    status, bal, _ = route_app_get(store, chain, f"/api/tokens/WEB/balance/{bob.segwit_address}", {})
    assert bal["amount"] == "2.00000000"

    status, holders, _ = route_app_get(store, chain, "/api/tokens/WEB/balances", {})
    assert holders["holder_count"] == 2

    status, events, _ = route_app_get(store, chain, "/api/tokens/WEB/events", {})
    assert [e["kind"] for e in events["events"]] == ["transfer", "create"]


def test_token_routes_served_over_http(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    alice = Wallet.create()
    chain.mine_block(alice.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        req = Request(
            f"{s.url}/api/tokens",
            data=json.dumps({"symbol": "HTTP", "creator": alice.segwit_address, "initial_supply": "7", "decimals": 0}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as res:
            created = json.loads(res.read().decode())
        assert created["symbol"] == "HTTP"
        listing = get(f"{s.url}/api/tokens")
        assert listing["count"] == 1
        bal = get(f"{s.url}/api/tokens/HTTP/balance/{alice.segwit_address}")
        assert bal["units"] == 7
