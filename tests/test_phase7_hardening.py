import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.apps import AppStore
from netcoin.chain import Blockchain
from netcoin.explorer_server import make_handler
from netcoin.wallet import Wallet


class capture_server:
    def __init__(self):
        self.received = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                outer.received.append({
                    "body": self.rfile.read(length).decode("utf-8"),
                    "signature": self.headers.get("X-Netcoin-Signature"),
                    "event": self.headers.get("X-Netcoin-Event"),
                })
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args, **kwargs):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class explorer_server:
    def __init__(self, chain: Blockchain):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(chain))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def post_json(url: str, body: dict, headers: dict | None = None):
    req = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, headers: dict | None = None):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_app_store_optional_sqlite_backend(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NETCOIN_APP_STORAGE", "sqlite")
    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    store = AppStore(chain.data_dir)
    created = store.upsert_username({"username": "alice", "address": wallet.address})
    assert created["username"] == "alice"
    assert (chain.data_dir / "app_layer.sqlite3").exists()

    reopened = AppStore(chain.data_dir)
    assert reopened.resolve_username("alice")["address"] == wallet.address
    assert reopened.security_status()["storage_backend"] == "sqlite"


def test_admin_token_gate_for_app_writes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NETCOIN_APP_REQUIRE_ADMIN", "1")
    monkeypatch.setenv("NETCOIN_APP_ADMIN_TOKEN", "secret-token")
    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    with explorer_server(chain) as srv:
        try:
            post_json(f"{srv.url}/api/profiles", {"username": "bob", "address": wallet.address})
            assert False, "expected admin auth failure"
        except HTTPError as exc:
            assert exc.code == 401
        ok = post_json(f"{srv.url}/api/profiles", {"username": "bob", "address": wallet.address}, headers={"X-Netcoin-Admin-Token": "secret-token"})
    assert ok["username"] == "bob"


def test_webhook_delivery_signature_and_retry_log(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    with capture_server() as hook:
        registered = store.register_webhook({"merchant_id": "m1", "url": hook.url, "events": ["payment.confirmed"]})
        event = store.queue_webhook_event({"merchant_id": "m1", "event": "payment.confirmed", "payload": {"invoice_id": "inv1"}})
        delivered = store.deliver_webhook_events({"max_events": 1})
    assert delivered["delivered"] == 1
    assert hook.received[0]["event"] == "payment.confirmed"
    assert hook.received[0]["signature"].startswith("sha256=")
    assert registered["secret_hash"]
    stored_event = next(e for e in store.load()["webhook_events"] if e["event_id"] == event["event_id"])
    assert stored_event["attempt_count"] == 1
    assert stored_event["delivered"] is True


def test_prediction_market_legal_ack_gate_and_restricted_topics(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NETCOIN_REQUIRE_MARKET_LEGAL_ACK", "1")
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    try:
        store.create_prediction_market({"question": "Will NetCoin mine 10 blocks?", "outcomes": ["YES", "NO"]})
        assert False, "expected legal acknowledgement failure"
    except Exception as exc:
        assert "legal_acknowledged" in str(exc)

    market = store.create_prediction_market({"question": "Will NetCoin mine 10 blocks?", "outcomes": ["YES", "NO"], "legal_acknowledged": True})
    assert market["legal_acknowledged"] is True

    try:
        store.create_prediction_market({"question": "Who wins the election?", "outcomes": ["A", "B"], "legal_acknowledged": True})
        assert False, "expected restricted topic failure"
    except Exception as exc:
        assert "restricted" in str(exc)


def test_payout_signing_policy_attaches_to_plans(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    store = AppStore(chain.data_dir)
    policy = store.set_payout_signing_policy({"mode": "offline_multisig_review", "max_auto_broadcast": "0.1", "notes": "production policy"})
    plan = store.plan_payout("test", [{"address": wallet.address, "amount": "0.2"}], memo="policy test")
    assert policy["mode"] == "offline_multisig_review"
    assert plan["signing_policy"]["mode"] == "offline_multisig_review"
    assert plan["requires_operator_review"] is True
