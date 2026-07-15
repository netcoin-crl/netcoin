from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from netcoin.apps import AppStore
from netcoin.chain import Blockchain


class _flaky_server:
    """A local webhook receiver that fails every request until `.fixed` is set."""

    def __init__(self):
        self.received = []
        self.fixed = False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                outer.received.append(self.rfile.read(length))
                if outer.fixed:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                else:
                    self.send_response(500)
                    self.end_headers()

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


def test_event_becomes_a_visible_dead_letter_after_exhausting_retries(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    with _flaky_server() as hook:
        store.register_webhook(
            {"merchant_id": "game-studio", "url": hook.url, "events": ["payment.confirmed"], "max_attempts": 2}
        )
        event = store.queue_webhook_event(
            {"merchant_id": "game-studio", "event": "payment.confirmed", "payload": {"invoice_id": "inv1"}}
        )
        # Exhaust the 2-attempt budget (force bypasses the exponential backoff wait).
        store.deliver_webhook_events({"max_events": 1, "force": True})
        store.deliver_webhook_events({"max_events": 1, "force": True})

    dead_letters = store.list_webhook_dead_letters()
    assert dead_letters["count"] == 1
    assert dead_letters["dead_letters"][0]["event_id"] == event["event_id"]
    assert len(dead_letters["dead_letters"][0]["attempts"]) == 2

    # scoped to a different developer_id, it must not show up
    scoped = store.list_webhook_dead_letters(developer_id="other-studio")
    assert scoped["count"] == 0


def test_retrying_a_single_dead_letter_by_event_id_clears_it_on_success(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    with _flaky_server() as hook:
        store.register_webhook(
            {"merchant_id": "game-studio", "url": hook.url, "events": ["payment.confirmed"], "max_attempts": 1}
        )
        event = store.queue_webhook_event(
            {"merchant_id": "game-studio", "event": "payment.confirmed", "payload": {"invoice_id": "inv2"}}
        )
        store.deliver_webhook_events({"max_events": 1, "force": True})
        assert store.list_webhook_dead_letters()["count"] == 1

        # fix the receiver, then retry just this one event by id — a targeted
        # retry must not require bumping max_attempts or waiting on backoff.
        hook.fixed = True
        result = store.deliver_webhook_events({"event_id": event["event_id"]})

    assert result["delivered"] == 1
    assert store.list_webhook_dead_letters()["count"] == 0
    stored = next(e for e in store.load()["webhook_events"] if e["event_id"] == event["event_id"])
    assert stored["delivered"] is True
    assert stored["dead_letter"] is False


def test_retry_by_event_id_does_not_touch_other_pending_events(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    with _flaky_server() as hook:
        store.register_webhook({"merchant_id": "game-studio", "url": hook.url, "events": ["payment.confirmed"]})
        target = store.queue_webhook_event(
            {"merchant_id": "game-studio", "event": "payment.confirmed", "payload": {"invoice_id": "target"}}
        )
        other = store.queue_webhook_event(
            {"merchant_id": "game-studio", "event": "payment.confirmed", "payload": {"invoice_id": "other"}}
        )
        hook.fixed = True
        result = store.deliver_webhook_events({"event_id": target["event_id"]})

    assert result["delivered"] == 1
    data = store.load()
    other_stored = next(e for e in data["webhook_events"] if e["event_id"] == other["event_id"])
    assert other_stored["delivered"] is False
