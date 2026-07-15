from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from netcoin.apps import AppStore
from netcoin.chain import Blockchain
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


class _capture_server:
    def __init__(self):
        self.received = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                import json as _json

                length = int(self.headers.get("Content-Length", "0"))
                outer.received.append(_json.loads(self.rfile.read(length).decode("utf-8")))
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


def test_a_ready_deposit_queues_a_webhook_event_the_first_time_it_is_seen(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    funder = Wallet.create()
    player = Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)

    store.register_watch_address({"developer_id": "game-studio", "address": player.address, "label": "deposit"})
    tx = funder.create_transaction(chain, player.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(funder.address)

    result = store.developer_deposits(chain, developer_id="game-studio")
    assert any(row["txid"] == tx.txid() and row["ready"] for row in result["deposits"])

    events = store.load()["webhook_events"]
    deposit_events = [e for e in events if e["event"] == "deposit.detected"]
    assert len(deposit_events) == 1
    assert deposit_events[0]["payload"]["txid"] == tx.txid()
    assert deposit_events[0]["payload"]["address"] == player.address


def test_the_same_deposit_does_not_queue_a_second_event_on_repeated_polls(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    funder = Wallet.create()
    player = Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)

    store.register_watch_address({"developer_id": "game-studio", "address": player.address})
    tx = funder.create_transaction(chain, player.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(funder.address)

    store.developer_deposits(chain, developer_id="game-studio")
    store.developer_deposits(chain, developer_id="game-studio")
    store.developer_deposits(chain, developer_id="game-studio")

    events = [e for e in store.load()["webhook_events"] if e["event"] == "deposit.detected"]
    assert len(events) == 1


def test_deposit_detected_event_actually_delivers_to_a_registered_webhook(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    funder = Wallet.create()
    player = Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)

    with _capture_server() as hook:
        store.register_webhook({"merchant_id": "game-studio", "url": hook.url, "events": ["deposit.detected"]})
        store.register_watch_address({"developer_id": "game-studio", "address": player.address})
        tx = funder.create_transaction(chain, player.address, amount_to_sats("2"), amount_to_sats("0.01"))
        chain.add_mempool_transaction(tx)
        chain.mine_block(funder.address)

        store.developer_deposits(chain, developer_id="game-studio")
        delivered = store.deliver_webhook_events({"max_events": 5})

    assert delivered["delivered"] == 1
    assert hook.received[0]["event"] == "deposit.detected"
    assert hook.received[0]["payload"]["txid"] == tx.txid()


def test_not_yet_confirmed_deposit_does_not_queue_an_event_until_ready(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    funder = Wallet.create()
    player = Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)

    store.register_watch_address(
        {"developer_id": "game-studio", "address": player.address, "confirmations_required": 3}
    )
    tx = funder.create_transaction(chain, player.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(funder.address)  # only 1 confirmation, requirement is 3

    result = store.developer_deposits(chain, developer_id="game-studio")
    assert any(row["txid"] == tx.txid() and not row["ready"] for row in result["deposits"])
    assert not [e for e in store.load()["webhook_events"] if e["event"] == "deposit.detected"]

    chain.mine_block(funder.address)
    chain.mine_block(funder.address)
    store.developer_deposits(chain, developer_id="game-studio")
    assert len([e for e in store.load()["webhook_events"] if e["event"] == "deposit.detected"]) == 1
