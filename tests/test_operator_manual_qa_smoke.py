"""End-to-end operator QA smoke test for the launch checklist.

This deliberately exercises the flows a human operator would click through before
publishing a testnet build: wallet funding/sending, invoices, receipts, merchant
webhooks, manual payout review, contract demos, SQLite persistence, and admin
route protection.
"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.apps import AppStore
from netcoin.apps.auth import SignedEnvelope, canonical_body_hash
from netcoin.chain import Blockchain
from netcoin.crypto import sign_message
from netcoin.explorer_server import make_handler
from netcoin.tx import amount_to_sats
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


def get_json(url: str, headers: dict[str, str] | None = None):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())


def post_json(url: str, payload: dict, headers: dict[str, str] | None = None):
    req = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())


def signed_payload(payload: dict, wallet: Wallet, path: str) -> dict:
    body = dict(payload)
    env = SignedEnvelope(
        address=wallet.segwit_address,
        method="POST",
        path=path,
        body_hash=canonical_body_hash(body),
        timestamp=int(time.time()),
        nonce=f"qa-{time.time_ns()}",
        signature="",
    )
    body["signed_envelope"] = {
        "address": env.address,
        "method": env.method,
        "path": env.path,
        "body_hash": env.body_hash,
        "timestamp": env.timestamp,
        "nonce": env.nonce,
        "signature": sign_message(wallet.private_key, env.message()),
    }
    return body


def fund_wallet(chain: Blockchain, miner: Wallet, blocks: int = 101) -> None:
    for _ in range(blocks):
        chain.mine_block(miner.address)


def test_operator_launch_manual_qa_flow(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NETCOIN_APP_STORAGE", "sqlite")
    monkeypatch.setenv("NETCOIN_APP_REQUIRE_ADMIN", "1")
    monkeypatch.setenv("NETCOIN_APP_ADMIN_TOKEN", "qa-secret")
    monkeypatch.setenv("NETCOIN_REQUIRE_MARKET_LEGAL_ACK", "1")

    # 1-4. Create wallets, fund them, save a contact/label, and send a payment.
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    merchant = Wallet.create()
    customer = Wallet.create()
    mediator = Wallet.create()
    store = AppStore(chain.data_dir)

    fund_wallet(chain, miner)
    assert chain.balances_for_address(miner.address)["spendable"] >= amount_to_sats("50")

    contact = store.upsert_known_label({"address": merchant.address, "label": "QA Merchant", "category": "merchant"})
    assert contact["label"] == "QA Merchant"

    first_tx = miner.create_transaction(chain, customer.address, amount_to_sats("2"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(first_tx)
    chain.mine_block(miner.address)
    assert chain.balances_for_address(customer.address)["total"] == amount_to_sats("2")

    # 5-7. Create an invoice, ensure old history does not auto-pay it, pay it, and view receipt.
    invoice = store.create_invoice(
        chain, {"address": merchant.address, "amount": "1.25", "memo": "QA checkout", "merchant_id": "shop"}
    )
    assert invoice["status"] == "unpaid"
    assert invoice["paid_total_sats"] == 0

    pay_tx = miner.create_transaction(chain, merchant.address, amount_to_sats("1.25"), amount_to_sats("0.01"))
    invoice_payment_txid = chain.add_mempool_transaction(pay_tx)
    pending = store.invoice_status(chain, invoice["invoice_id"])
    assert pending["status"] in {"pending", "confirmed"}
    chain.mine_block(miner.address)
    paid = store.invoice_status(chain, invoice["invoice_id"])
    assert paid["status"] == "confirmed"
    assert paid["receipt_txid"] == invoice_payment_txid
    receipt = store.receipt(chain, invoice_payment_txid)
    assert receipt["confirmed"] is True
    assert merchant.address in receipt["outputs_to_address_sats"]

    # 8 and 18. Create a merchant API key, register a webhook, and deliver a signed test event.
    store.create_api_key({"merchant_id": "shop", "permissions": ["*"]})
    store.set_api_key_enforcement({"merchant_id": "shop", "required": True})
    received: list[dict[str, str | bytes | None]] = []

    class Hook(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append({"body": body, "sig": self.headers.get("X-Netcoin-Signature")})
            self.send_response(204)
            self.end_headers()

    with Served(Hook) as hook:
        registered = store.register_webhook(
            {"merchant_id": "shop", "url": hook.url, "events": ["payment.confirmed"], "secret": "whsec"}
        )
        store.queue_webhook_event(
            {"merchant_id": "shop", "event": "payment.confirmed", "payload": {"invoice_id": invoice["invoice_id"]}}
        )
        delivered = store.deliver_webhook_events({"timeout": 2})
    assert registered["webhook_id"]
    assert delivered["delivered"] >= 1
    assert received and str(received[0]["sig"]).startswith("sha256=")

    # 9-13. Create a payout plan, approve it, export a signer bundle, record signed tx and broadcast txid through admin APIs.
    reward = store.create_reward({"address": customer.address, "amount": "0.5", "reason": "QA reward"})
    payout_id = reward["payout_plan"]["payout_id"]
    with Served(make_handler(chain)) as srv:
        try:
            get_json(f"{srv.url}/api/admin/summary")
            assert False, "admin summary should require a token"
        except HTTPError as exc:
            assert exc.code == 401
        headers = {"X-Netcoin-Admin-Token": "qa-secret"}
        summary = get_json(f"{srv.url}/api/admin/summary", headers=headers)
        assert summary["counts"]["payout_plans"] >= 1
        review = post_json(
            f"{srv.url}/api/admin/payouts/{payout_id}/review",
            signed_payload({"reviewer": "qa"}, miner, f"/admin/payouts/{payout_id}/review"),
            headers=headers,
        )
        bundle = get_json(f"{srv.url}/api/admin/payouts/{payout_id}/bundle", headers=headers)
        signed = post_json(
            f"{srv.url}/api/admin/payouts/{payout_id}/signed",
            signed_payload({"txid": "signedqa", "signer": "offline"}, miner, f"/admin/payouts/{payout_id}/signed"),
            headers=headers,
        )
        broadcasted = post_json(
            f"{srv.url}/api/admin/payouts/{payout_id}/broadcasted",
            signed_payload({"txid": "broadcastqa", "operator": "qa"}, miner, f"/admin/payouts/{payout_id}/broadcasted"),
            headers=headers,
        )
    assert review["status"] == "ready_for_wallet_signing"
    assert bundle["payout_plan"]["payout_id"] == payout_id
    assert signed["status"] == "signed_ready_to_broadcast"
    assert broadcasted["status"] == "broadcast_recorded"

    # 14. Recurring agreement creates an invoice and records a payment.
    recurring = store.create_recurring_agreement(
        {"payer": customer.address, "recipient": merchant.address, "amount": "0.25", "interval": "monthly"}
    )
    recurring_invoice = store.create_recurring_invoice(chain, recurring["agreement_id"], {"memo": "QA recurring"})
    assert recurring_invoice["order_id"] == recurring["agreement_id"]
    recurring_paid = store.record_recurring_payment(recurring["agreement_id"], {"txid": invoice_payment_txid})
    assert recurring_paid["last_payment_txid"] == invoice_payment_txid

    # 15. Escrow creates a 2-of-3 address and requires two approvals for a payout plan.
    escrow_stub = store.create_escrow(
        chain,
        {
            "buyer_pubkey": customer.public_key_hex,
            "seller_pubkey": merchant.public_key_hex,
            "mediator_pubkey": mediator.public_key_hex,
            "buyer_address": customer.address,
            "seller_address": merchant.address,
            "mediator_address": mediator.address,
            "amount": "0.75",
            "terms": "QA escrow terms",
        }
    )
    escrow_fund_block = chain.mine_block(escrow_stub["escrow_address"])
    edata = store.load()
    edata["escrows"][escrow_stub["escrow_id"]]["funding_txid"] = escrow_fund_block.transactions[0].txid()
    store.save(edata)
    escrow = store.escrow_status(chain, escrow_stub["escrow_id"])
    assert escrow["status"] == "funded"
    first_release = store.escrow_action(
        chain, escrow["escrow_id"], {"action": "release", "signer": "buyer", "to_address": merchant.address}
    )
    assert first_release["status"] == "pending_release"
    second_release = store.escrow_action(
        chain, escrow["escrow_id"], {"action": "release", "signer": "mediator", "to_address": merchant.address}
    )
    assert second_release["status"] == "released"
    assert second_release["payout_plan"]["kind"] == "escrow_release"

    # 16. Signed-message poll vote.
    poll = store.create_poll({"title": "Ship QA build?", "options": ["Yes", "No"], "creator_address": miner.address})
    option_id = poll["options"][0]["option_id"]
    vote_message = store.poll_vote_message(poll["poll_id"], option_id)
    vote_sig = sign_message(miner.private_key, vote_message)
    voted = store.cast_poll_vote(
        poll["poll_id"], {"voter_address": miner.address, "option_id": option_id, "signature": vote_sig}
    )
    assert voted["vote_count"] == 1
    assert voted["winner_option_id"] == option_id

    # 17. Testnet/demo prediction market, order matching, and resolution payout plan.
    market = store.create_prediction_market(
        {"question": "Will QA pass?", "outcomes": ["YES", "NO"], "legal_acknowledged": True}
    )
    outcome_id = market["outcomes"][0]["outcome_id"]
    store.place_market_order(
        market["market_id"],
        {"address": merchant.address, "outcome_id": outcome_id, "side": "sell", "quantity": 3, "price_bps": 4000},
    )
    traded = store.place_market_order(
        market["market_id"],
        {"address": customer.address, "outcome_id": outcome_id, "side": "buy", "quantity": 3, "price_bps": 5000},
    )
    assert len(traded["trades"]) == 1
    resolved = store.resolve_prediction_market(
        market["market_id"], {"winning_outcome_id": outcome_id, "payout_per_share": "0.1"}
    )
    assert resolved["status"] == "resolved"
    assert resolved["payout_plan"]["kind"] == "prediction_market"

    # Wallet safety controls and statements from the checklist.
    store.set_spending_limits(
        {"wallet_id": "qa-wallet", "single_tx_limit": "1", "daily_limit": "2", "require_backup": True}
    )
    assert (
        store.check_spending_limits(
            {"wallet_id": "qa-wallet", "address": customer.address, "amount": "1.5", "fee": "0.01"}
        )["ok"]
        is False
    )
    store.set_backup_health({"wallet_id": "qa-wallet", "seed_verified": True, "encrypted_export_saved": True})
    assert (
        store.check_spending_limits(
            {"wallet_id": "qa-wallet", "address": customer.address, "amount": "0.5", "fee": "0.01"}
        )["ok"]
        is True
    )
    assert store.wallet_statement_pdf(chain, merchant.address).startswith(b"%PDF")

    # 19. Restart/persistence with SQLite retains app-layer records.
    reloaded_store = AppStore(chain.data_dir)
    assert (
        reloaded_store.resolve_username(
            store.upsert_username({"username": "qamerchant", "address": merchant.address})["username"]
        )["address"]
        == merchant.address
    )
    assert reloaded_store.invoice_status(chain, invoice["invoice_id"])["status"] == "confirmed"
    assert reloaded_store.get_payout_plan(payout_id)["broadcast_txid"] == "broadcastqa"

    # 20. Security/status endpoints work with admin token and admin routes reject without it above.
    status = reloaded_store.security_status()
    assert status["storage_backend"] in {"sqlite", "sqlite3"}
    assert status["admin_token_required"] is True
