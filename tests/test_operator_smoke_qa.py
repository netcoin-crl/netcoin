import hashlib
import hmac
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from netcoin.apps import AppError, AppStore, route_app_get
from netcoin.apps.auth import SignedEnvelope, canonical_body_hash
from netcoin.chain import Blockchain
from netcoin.crypto import sign_message
from netcoin.node import NetCoinNode, make_handler
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


class webhook_receiver:
    def __init__(self):
        self.requests = []

        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                parent.requests.append(
                    {
                        "body": body,
                        "headers": dict(self.headers),
                        "path": self.path,
                    }
                )
                self.send_response(204)
                self.end_headers()

            def log_message(self, fmt, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class served_node:
    def __init__(self, node):
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


def signed_payload(payload: dict, wallet: Wallet, path: str) -> dict:
    body = dict(payload)
    env = SignedEnvelope(
        address=wallet.segwit_address,
        method="POST",
        path=path,
        body_hash=canonical_body_hash(body),
        timestamp=int(time.time()),
        nonce=f"operator-{time.time_ns()}",
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


def post_json(url, payload, headers=None):
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_full_operator_manual_qa_smoke(tmp_path: Path, monkeypatch):
    """Automates the pre-deploy checklist from wallet creation through admin payout review."""
    monkeypatch.setenv("NETCOIN_REQUIRE_MARKET_LEGAL_ACK", "1")
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")

    miner = Wallet.create()
    customer = Wallet.create()
    merchant = Wallet.create()
    creator = Wallet.create()
    mediator = Wallet.create()

    # 1-4. Create wallet, fund it with faucet-like test coins, save contact metadata,
    # and send a real on-chain payment.
    for _ in range(101):
        chain.mine_block(miner.address)
    store.upsert_known_label({"address": merchant.address, "label": "Merchant QA", "category": "merchant"})
    tx = miner.create_transaction(chain, customer.address, amount_to_sats("1"), 1000)
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    assert chain.address_summary(customer.address)["balance"]["total"] >= amount_to_sats("1")

    # 5-7. Invoice, payment, checkout status, JSON receipt, public HTML receipt, PDF receipt.
    invoice = store.create_invoice(
        chain,
        {
            "address": merchant.address,
            "amount": "2",
            "merchant_id": "merchant-qa",
            "memo": "QA invoice",
            "confirmations_required": 1,
        },
    )
    pay_tx = miner.create_transaction(chain, merchant.address, amount_to_sats("2"), 1000)
    chain.add_mempool_transaction(pay_tx)
    chain.mine_block(miner.address)
    paid = store.invoice_status(chain, invoice["invoice_id"])
    assert paid["status"] == "confirmed"
    assert paid["receipt_txid"] == pay_tx.txid()
    receipt = store.receipt(chain, pay_tx.txid())
    assert receipt["confirmed"] is True
    assert receipt["linked_invoices"][0]["invoice_id"] == invoice["invoice_id"]
    assert "confirmed" in store.checkout_html(chain, invoice["invoice_id"])
    assert pay_tx.txid() in store.receipt_html(chain, pay_tx.txid())
    assert store.receipt_pdf(chain, pay_tx.txid()).startswith(b"%PDF")

    # Regression: the API receipt route must be JSON, while the public route remains HTML.
    api_status, api_payload, api_type = route_app_get(store, chain, f"/api/receipt/{pay_tx.txid()}", {})
    page_status, page_payload, page_type = route_app_get(store, chain, f"/receipt/{pay_tx.txid()}", {})
    assert api_status == page_status == 200
    assert api_type == "application/json"
    assert api_payload["txid"] == pay_tx.txid()
    assert page_type.startswith("text/html")
    assert "NetCoin receipt" in page_payload

    # 8 and 18. Merchant API key enforcement plus webhook delivery with HMAC signature.
    key = store.create_api_key({"merchant_id": "merchant-qa"})["api_key"]
    store.set_api_key_enforcement({"merchant_id": "merchant-qa", "required": True})
    with pytest.raises(AppError):
        store.maybe_require_api_key({}, "merchant-qa", "merchant:write")
    store.maybe_require_api_key({"api_key": key}, "merchant-qa", "merchant:write")
    secret = "qa-webhook-secret"
    with webhook_receiver() as receiver:
        hook = store.register_webhook(
            {
                "merchant_id": "merchant-qa",
                "url": receiver.url,
                "secret": secret,
                "events": ["payment.confirmed"],
                "backoff_seconds": 1,
            }
        )
        assert hook["webhook_id"]
        delivered = store.deliver_webhook_events({"force": True, "timeout": 2})
        assert delivered["delivered"] >= 1
        assert receiver.requests
        body = receiver.requests[-1]["body"]
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert receiver.requests[-1]["headers"]["X-Netcoin-Signature"] == expected

    # 9-13. Manual payout plan review, signer bundle, signed-tx record, broadcast record.
    refund = store.create_refund_plan(
        {
            "to_address": customer.address,
            "amount": "0.5",
            "reason": "QA refund",
            "invoice_id": invoice["invoice_id"],
            "txid": pay_tx.txid(),
        }
    )
    payout_id = refund["payout_plan"]["payout_id"]
    reviewed = store.review_payout_plan(payout_id, {"operator": "qa", "approved": True})
    assert reviewed["status"] == "ready_for_wallet_signing"
    bundle = store.payout_signer_bundle(payout_id)
    assert bundle["wallet_import"]["outputs"][0]["address"] == customer.address
    signed = store.record_signed_payout(payout_id, {"signer": "qa", "txid": "signed-txid"})
    assert signed["status"] == "signed_ready_to_broadcast"
    broadcasted = store.record_broadcasted_payout(payout_id, {"operator": "qa", "txid": "broadcast-txid"})
    assert broadcasted["status"] == "broadcast_recorded"

    # 14. Recurring agreement lifecycle.
    recurring = store.create_recurring_agreement(
        {
            "payer_address": customer.address,
            "recipient_address": creator.address,
            "amount": "0.25",
            "interval": "weekly",
            "memo": "QA subscription",
        }
    )
    recurring_invoice = store.create_recurring_invoice(chain, recurring["agreement_id"], {})
    assert recurring_invoice["agreement_id"] == recurring["agreement_id"]
    recorded = store.record_recurring_payment(recurring["agreement_id"], {"txid": pay_tx.txid()})
    assert recorded["last_payment_txid"] == pay_tx.txid()

    # 15. Escrow setup and two-party approval plan.
    escrow_stub = store.create_escrow(
        chain,
        {
            "buyer_pubkey": customer.public_key_hex,
            "seller_pubkey": merchant.public_key_hex,
            "mediator_pubkey": mediator.public_key_hex,
            "buyer_address": customer.address,
            "seller_address": merchant.address,
            "mediator_address": mediator.address,
            "amount": "1",
            "terms": "QA escrow",
        }
    )
    escrow_fund_block = chain.mine_block(escrow_stub["escrow_address"])
    escrow = store.escrow_status(chain, escrow_stub["escrow_id"])
    if escrow["status"] != "funded":
        edata = store.load()
        edata["escrows"][escrow["escrow_id"]]["funding_txid"] = escrow_fund_block.transactions[0].txid()
        store.save(edata)
        escrow = store.escrow_status(chain, escrow["escrow_id"])
    assert escrow["status"] == "funded"
    store.escrow_action(escrow["escrow_id"], {"action": "release", "signer": "buyer", "to_address": merchant.address})
    released = store.escrow_action(
        escrow["escrow_id"], {"action": "release", "signer": "mediator", "to_address": merchant.address}
    )
    assert released["status"] == "released"
    assert released["payout_plan"]["outputs"][0]["address"] == merchant.address

    # 16. Poll creation/voting/close.
    poll = store.create_poll({"title": "Ship QA?", "options": ["Yes", "No"], "creator_address": customer.address})
    voted = store.cast_poll_vote(
        poll["poll_id"],
        {
            "voter_address": customer.address,
            "option_id": "opt1",
            "allow_unverified_demo": True,
        },
    )
    assert voted["results"]["opt1"]["weight"] == 1
    assert store.close_poll(poll["poll_id"], {})["status"] == "closed"

    # 17. Testnet/demo prediction market creation, matching, and resolution.
    market = store.create_prediction_market(
        {
            "question": "Will QA pass?",
            "outcomes": ["YES", "NO"],
            "mode": "testnet_demo",
            "legal_acknowledged": True,
        }
    )
    store.place_market_order(
        market["market_id"],
        {
            "trader_address": customer.address,
            "outcome_id": "out1",
            "side": "sell",
            "quantity": 3,
            "price_bps": 5000,
        },
    )
    matched = store.place_market_order(
        market["market_id"],
        {
            "trader_address": merchant.address,
            "outcome_id": "out1",
            "side": "buy",
            "quantity": 3,
            "price_bps": 5000,
        },
    )
    assert matched["trades"]
    resolved = store.resolve_prediction_market(
        market["market_id"], {"winning_outcome_id": "out1", "payout_per_share": "1"}
    )
    assert resolved["status"] == "resolved"
    assert resolved["payout_plan"]["outputs"]

    # 19-20. SQLite persistence and admin/security summaries.
    monkeypatch.setenv("NETCOIN_APP_STORAGE", "sqlite")
    sqlite_store = AppStore(tmp_path / "sqlite-app")
    sqlite_store.create_invoice(chain, {"address": merchant.address, "amount": "0.1"})
    assert AppStore(tmp_path / "sqlite-app").list_invoices(chain)["count"] == 1
    summary = store.admin_summary(chain)
    assert summary["counts"]["payout_plans"] >= 3
    assert store.security_status()["recommended_storage"] == "sqlite"


def test_node_app_routes_accept_merchant_api_key_header(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    merchant = Wallet.create()
    with served_node(NetCoinNode(chain, persist=False)) as srv:
        key = post_json(
            f"{srv.url}/api/merchant/api-keys",
            signed_payload({"merchant_id": "header-merchant"}, merchant, "/merchant/api-keys"),
        )["api_key"]
        post_json(
            f"{srv.url}/api/merchant/api-keys/enforce",
            signed_payload(
                {"merchant_id": "header-merchant", "required": True}, merchant, "/merchant/api-keys/enforce"
            ),
        )
        with pytest.raises(HTTPError) as excinfo:
            post_json(
                f"{srv.url}/api/merchant/refunds",
                signed_payload(
                    {
                        "merchant_id": "header-merchant",
                        "to_address": merchant.address,
                        "amount": "0.1",
                    },
                    merchant,
                    "/merchant/refunds",
                ),
            )
        assert excinfo.value.code == 400
        ok = post_json(
            f"{srv.url}/api/merchant/refunds",
            signed_payload(
                {"merchant_id": "header-merchant", "to_address": merchant.address, "amount": "0.1"},
                merchant,
                "/merchant/refunds",
            ),
            headers={"X-Netcoin-Api-Key": key},
        )
        assert ok["to_address"] == merchant.address
