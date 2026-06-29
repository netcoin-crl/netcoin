import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

from netcoin.apps import AppStore, validate_address_payload
from netcoin.chain import Blockchain
from netcoin.explorer_server import make_handler as make_explorer_handler
from netcoin.node import NetCoinNode, make_handler as make_node_handler
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


class served:
    def __init__(self, handler):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def get_json(url: str):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict):
    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def mature_wallet(chain: Blockchain, wallet: Wallet, blocks: int = 101) -> None:
    for _ in range(blocks):
        chain.mine_block(wallet.address)


def pay_address(chain: Blockchain, payer: Wallet, recipient_address: str, amount: str = "1"):
    tx = payer.create_transaction(chain, recipient_address, amount_to_sats(amount), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(payer.address)
    return tx


def test_app_store_invoice_username_merchant_community_wallet_and_network(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    payer = Wallet.create()
    merchant = Wallet.create()
    mature_wallet(chain, payer)
    store = AppStore(chain.data_dir)

    assert validate_address_payload(merchant.address)["valid"] is True

    inv = store.create_invoice(chain, {"address": merchant.address, "amount": "1", "memo": "order"})
    assert inv["status"] == "unpaid"
    tx = pay_address(chain, payer, merchant.address, "1")
    paid = store.invoice_status(chain, inv["invoice_id"])
    assert paid["status"] == "confirmed"
    assert paid["paid_total_sats"] >= 100_000_000
    assert paid["receipt_txid"] == tx.txid()
    assert paid["payment_uri"].startswith("netcoin:")

    username = store.upsert_username({"username": "contributor", "address": merchant.address, "display_name": "contributor"})
    assert username["address"] == merchant.address
    assert store.resolve_username("contributor")["display_name"] == "contributor"

    api_key = store.create_api_key({"merchant_id": "shop"})
    assert api_key["api_key"].startswith("nck_")
    hook = store.register_webhook({"merchant_id": "shop", "url": "https://example.com/hook"})
    assert hook["webhook_id"]

    gift = store.create_gift({"amount": "0.5", "memo": "welcome"})
    claimed = store.claim_gift({"claim_code": gift["claim_code"], "address": merchant.address})
    assert claimed["status"] == "claimed"

    airdrop = store.airdrop({"addresses": [merchant.address, "bad"], "amount": "0.1"})
    assert airdrop["valid_count"] == 1
    bounty = store.create_bounty({"title": "bug", "reward": "2"})
    awarded = store.award_bounty(bounty["bounty_id"], {"address": merchant.address})
    assert awarded["winner_address"] == merchant.address

    statement = store.wallet_statement(chain, payer.address)
    assert statement["transaction_count"] >= 1
    assert store.network_health(chain)["height"] >= 102
    assert store.mining_dashboard(chain)["top_miners"]
    assert "blocks_remaining" in store.reward_countdown(chain)


def test_node_app_layer_routes(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    payer = Wallet.create()
    merchant = Wallet.create()
    mature_wallet(chain, payer)
    node = NetCoinNode(chain, persist=False)
    with served(make_node_handler(node)) as s:
        valid = get_json(f"{s.url}/validate-address?address={merchant.address}")
        inv = post_json(f"{s.url}/invoices", {"address": merchant.address, "amount": "1"})
        pay_address(chain, payer, merchant.address, "1")
        fetched = get_json(f"{s.url}/invoices/{inv['invoice_id']}")
        username = post_json(f"{s.url}/usernames", {"username": "netshop", "address": merchant.address})
        network = get_json(f"{s.url}/network")
    assert valid["valid"] is True
    assert fetched["status"] == "confirmed"
    assert username["username"] == "netshop"
    assert network["height"] >= 102


def test_explorer_api_prefixed_app_layer_routes(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    payer = Wallet.create()
    merchant = Wallet.create()
    mature_wallet(chain, payer)
    with served(make_explorer_handler(chain)) as s:
        inv = post_json(f"{s.url}/api/invoices", {"address": merchant.address, "amount": "1"})
        pay_address(chain, payer, merchant.address, "1")
        checkout = get_json(f"{s.url}/api/checkout/{inv['invoice_id']}")
        labels = post_json(f"{s.url}/api/labels", {"address": merchant.address, "label": "Merchant", "verified": True})
        statement = get_json(f"{s.url}/api/wallet/statement?address={payer.address}")
        community = get_json(f"{s.url}/api/community/leaderboards")
    assert checkout["checkout"]["status"] == "confirmed"
    assert labels["label"] == "Merchant"
    assert statement["address"] == payer.address
    assert "top_miners" in community
