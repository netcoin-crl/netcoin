import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.explorer_server import make_handler
from netcoin.wallet import Wallet


class Served:
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


def post_json(url: str, payload: dict):
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())


def get_bytes(url: str):
    with urlopen(url, timeout=5) as response:
        return response.info().get_content_type(), response.read()


def test_public_pages_pdfs_and_profiles(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    merchant = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    store = AppStore(chain.data_dir)
    inv = store.create_invoice(chain, {"address": merchant.address, "amount": "1", "memo": "checkout"})
    # Historical miner deposits must not auto-pay a fresh merchant invoice; pay it after creation.
    assert inv["status"] == "unpaid"
    tx = miner.create_transaction(chain, merchant.address, 100_000_000, 1_000_000)
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    paid = store.invoice_status(chain, inv["invoice_id"])
    txid = paid["receipt_txid"]
    store.upsert_username({"username": "contributor", "address": merchant.address, "display_name": "contributor", "bio": "NetCoin"})

    assert "NetCoin checkout" in store.checkout_html(chain, inv["invoice_id"])
    assert merchant.address in store.profile_html("contributor")
    assert "Embed button" in store.tip_html("contributor")
    assert txid in store.receipt_html(chain, txid)
    assert store.receipt_pdf(chain, txid).startswith(b"%PDF")
    assert store.wallet_statement_pdf(chain, merchant.address).startswith(b"%PDF")


def test_merchant_auth_webhook_delivery_and_refund_plan(tmp_path: Path):
    received = []

    class Hook(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append({"body": body, "sig": self.headers.get("X-Netcoin-Signature")})
            self.send_response(204)
            self.end_headers()

    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    store = AppStore(chain.data_dir)
    key = store.create_api_key({"merchant_id": "shop", "permissions": ["*"]})
    store.set_api_key_enforcement({"merchant_id": "shop", "required": True})
    with pytest.raises(AppError, match="API key"):
        store.maybe_require_api_key({}, "shop", "merchant:write")
    store.verify_api_key(key["api_key"], merchant_id="shop", permission="merchant:write")

    with Served(Hook) as hook:
        store.register_webhook({"merchant_id": "shop", "url": hook.url, "events": ["payment.confirmed"], "secret": "secret"})
        store.queue_webhook_event({"merchant_id": "shop", "event": "payment.confirmed", "payload": {"ok": True}})
        delivered = store.deliver_webhook_events({"timeout": 2})

    assert delivered["delivered"] == 1
    assert received and received[0]["sig"].startswith("sha256=")
    refund = store.create_refund_plan({"to_address": miner.address, "amount": "0.25", "reason": "customer refund"})
    assert refund["payout_plan"]["kind"] == "refund"


def test_community_payout_plans_rewards_and_tip_buttons(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    store = AppStore(chain.data_dir)

    airdrop = store.airdrop({"addresses": [miner.address], "amount": "0.1", "dry_run": False})
    assert airdrop["payout_plan"]["kind"] == "airdrop"
    gift = store.create_gift({"amount": "0.2", "funded": True})
    claimed = store.claim_gift({"claim_code": gift["claim_code"], "address": miner.address})
    assert claimed["payout_plan"]["kind"] == "gift"
    bounty = store.create_bounty({"title": "fix", "reward": "1"})
    awarded = store.award_bounty(bounty["bounty_id"], {"address": miner.address})
    assert awarded["payout_plan"]["kind"] == "bounty"
    reward = store.create_reward({"address": miner.address, "amount": "0.3", "reason": "testing"})
    assert reward["payout_plan"]["kind"] == "reward"
    button = store.tip_button({"address": miner.address, "label": "Tip contributor"})
    assert "netcoin:" in button["html"]


def test_wallet_limits_alerts_team_wallet_and_rotation(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    store = AppStore(chain.data_dir)

    store.set_spending_limits({"wallet_id": "w1", "single_tx_limit": "1", "daily_limit": "2", "require_backup": True})
    rejected = store.check_spending_limits({"wallet_id": "w1", "address": miner.address, "amount": "1.5", "fee": "0.01"})
    assert rejected["ok"] is False
    store.set_backup_health({"wallet_id": "w1", "seed_verified": True, "encrypted_export_saved": True})
    allowed = store.check_spending_limits({"wallet_id": "w1", "address": miner.address, "amount": "0.5", "fee": "0.01"})
    assert allowed["ok"] is True
    spent = store.record_wallet_spend({"wallet_id": "w1", "amount": "0.5", "fee": "0.01"})
    assert spent["spent_today_sats"] > 0

    alert = store.upsert_alert({"address": miner.address, "kind": "balance_above", "threshold": "0.01"})
    events = store.evaluate_alerts(chain)
    assert events["triggered"] >= 1

    team = store.create_team_wallet({"wallet_id": "team1", "required_approvals": 2})
    proposal = store.create_team_proposal(team["wallet_id"], {"to_address": miner.address, "amount": "0.1"})
    first = store.approve_team_proposal("team1", proposal["proposal_id"], {"member": "alice"})
    assert first["status"] == "pending_approval"
    second = store.approve_team_proposal("team1", proposal["proposal_id"], {"member": "bob"})
    assert second["status"] == "approved_ready_for_signing"

    rec = store.address_rotation_record({"wallet_id": "w1", "address": miner.address, "label": "first"})
    assert store.next_receive_address("w1")["address"] == rec["address"]


def test_explorer_serves_public_checkout_and_pdf(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    with Served(make_handler(chain)) as s:
        inv = post_json(f"{s.url}/api/invoices", {"address": miner.address, "amount": "1"})
        ctype, page = get_bytes(f"{s.url}/pay/{inv['invoice_id']}")
        pdf_type, pdf = get_bytes(f"{s.url}/api/wallet/statement.pdf?address={miner.address}")
    assert ctype == "text/html"
    assert b"NetCoin checkout" in page
    assert pdf_type == "application/pdf"
    assert pdf.startswith(b"%PDF")
