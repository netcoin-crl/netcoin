#!/usr/bin/env python3
"""Run a local NetCoin deployment-readiness QA flow.

This script exercises the practical testnet/operator flows without requiring
external services or real secrets. It uses a temporary chain, SQLite app-layer
storage, local HTTP servers, and manual-signing payout records.
"""

from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

import argparse
import contextlib
import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.apps import AppStore  # noqa: E402
from netcoin.chain import Blockchain  # noqa: E402
from netcoin.crypto import sign_message  # noqa: E402
from netcoin.explorer_server import make_handler as make_explorer_handler  # noqa: E402
from netcoin.tx import amount_to_sats  # noqa: E402
from netcoin.wallet import Wallet  # noqa: E402


class QAError(RuntimeError):
    pass


class QAReport:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.items.append({"name": name, "ok": True, "detail": detail})

    def fail(self, name: str, detail: str) -> None:
        self.items.append({"name": name, "ok": False, "detail": detail})
        raise QAError(f"{name}: {detail}")

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail or "condition was false")

    def to_dict(self) -> dict[str, Any]:
        return {"ok": all(x["ok"] for x in self.items), "checks": self.items, "count": len(self.items)}


class Served:
    def __init__(self, handler: type[BaseHTTPRequestHandler]):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> Served:
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@contextlib.contextmanager
def webhook_capture():
    received: list[dict[str, Any]] = []

    class HookHandler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            received.append(
                {
                    "headers": dict(self.headers),
                    "body": json.loads(body.decode("utf-8")),
                }
            )
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), HookHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/hook", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def http_json(
    url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, Any]]:
    data = None
    method = "GET"
    req_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        req_headers.setdefault("Content-Type", "application/json")
    req = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8"))


def mine_mature_funds(chain: Blockchain, wallet: Wallet, blocks: int = 101) -> None:
    for _ in range(blocks):
        chain.mine_block(wallet.address)


def send_and_mine(chain: Blockchain, sender: Wallet, recipient_address: str, amount: str, fee: str = "0.01"):
    tx = sender.create_transaction(chain, recipient_address, amount_to_sats(amount), amount_to_sats(fee))
    chain.add_mempool_transaction(tx)
    chain.mine_block(sender.address)
    return tx


def run_qa(base_dir: Path) -> QAReport:
    report = QAReport()
    old_storage = os.environ.get("NETCOIN_APP_STORAGE")
    old_require_admin = os.environ.get("NETCOIN_APP_REQUIRE_ADMIN")
    old_admin_token = os.environ.get("NETCOIN_APP_ADMIN_TOKEN")
    old_market_ack = os.environ.get("NETCOIN_REQUIRE_MARKET_LEGAL_ACK")
    try:
        os.environ["NETCOIN_APP_STORAGE"] = "sqlite"
        os.environ["NETCOIN_REQUIRE_MARKET_LEGAL_ACK"] = "1"
        chain = Blockchain(base_dir / "chain")
        store = AppStore(chain.data_dir)

        operator = Wallet.create()
        customer = Wallet.create()
        merchant = Wallet.create()
        seller = Wallet.create()
        mediator = Wallet.create()
        voter = Wallet.create()
        trader_yes = Wallet.create()
        trader_no = Wallet.create()

        mine_mature_funds(chain, operator)
        report.check(
            "1. Create wallet",
            all(w.address for w in [operator, customer, merchant]),
            "operator/customer/merchant wallets created",
        )

        faucet_tx = send_and_mine(chain, operator, customer.address, "20")
        report.check(
            "2. Get faucet coins",
            chain.address_balance_summary(customer.address)["total_sats"] >= amount_to_sats("20"),
            faucet_tx.txid(),
        )

        label = store.upsert_known_label(
            {"address": merchant.address, "label": "QA Merchant", "group": "Merchants", "verified": True}
        )
        wallet_js = (ROOT / "webwallet-browser" / "public" / "wallet-app.js").read_text(encoding="utf-8")
        report.check(
            "3. Save contact",
            label["label"] == "QA Merchant" and "ncw.contacts.v1" in wallet_js,
            "known label stored and wallet contact storage key present",
        )

        direct_tx = send_and_mine(chain, customer, merchant.address, "1")
        report.check("4. Send payment", chain.get_transaction(direct_tx.txid()) is not None, direct_tx.txid())

        invoice = store.create_invoice(
            chain, {"address": merchant.address, "amount": "2", "memo": "QA invoice", "merchant_id": "qa-shop"}
        )
        report.check("5. Create invoice", invoice["status"] == "unpaid", invoice["invoice_id"])

        pay_tx = send_and_mine(chain, customer, merchant.address, "2")
        paid_invoice = store.invoice_status(chain, invoice["invoice_id"])
        report.check(
            "6. Pay invoice",
            paid_invoice["status"] == "confirmed" and paid_invoice["receipt_txid"] == pay_tx.txid(),
            pay_tx.txid(),
        )

        receipt = store.receipt(chain, pay_tx.txid())
        report.check(
            "7. View receipt",
            receipt["confirmed"] is True and receipt["txid"] == pay_tx.txid(),
            f"confirmations={receipt['confirmations']}",
        )

        api_key = store.create_api_key({"merchant_id": "qa-shop", "permissions": ["merchant:write"]})
        store.set_api_key_enforcement({"merchant_id": "qa-shop", "required": True})
        store.verify_api_key(api_key["api_key"], merchant_id="qa-shop", permission="merchant:write")
        report.check("8. Create merchant API key", api_key["api_key"].startswith("nck_"), api_key["key_id"])

        refund = store.create_refund_plan(
            {
                "merchant_id": "qa-shop",
                "to_address": customer.address,
                "amount": "0.5",
                "reason": "QA refund",
                "api_key": api_key["api_key"],
            }
        )
        payout_id = refund["payout_plan"]["payout_id"]
        report.check("9. Create payout plan", refund["payout_plan"]["status"] == "pending_operator_review", payout_id)

        reviewed = store.review_payout_plan(payout_id, {"reviewer": "qa-operator", "approved": True})
        report.check(
            "10. Approve payout in admin dashboard", reviewed["status"] == "ready_for_wallet_signing", payout_id
        )

        bundle = store.payout_signer_bundle(payout_id)
        report.check(
            "11. Export signer bundle",
            bundle["wallet_import"]["outputs"],
            f"outputs={len(bundle['wallet_import']['outputs'])}",
        )

        signed = store.record_signed_payout(payout_id, {"operator": "qa-operator", "signed_txid": "qa-signed-txid"})
        report.check(
            "12. Record signed tx", signed["status"] == "signed_ready_to_broadcast", signed.get("signed_txid", "")
        )

        broadcasted = store.record_broadcasted_payout(
            payout_id, {"operator": "qa-operator", "txid": "qa-broadcast-txid"}
        )
        report.check(
            "13. Record broadcast txid", broadcasted["status"] == "broadcast_recorded", broadcasted["broadcast_txid"]
        )

        recurring = store.create_recurring_agreement(
            {
                "payer": customer.address,
                "recipient": merchant.address,
                "amount": "1",
                "interval": "monthly",
                "memo": "QA recurring",
            }
        )
        recurring_invoice = store.create_recurring_invoice(chain, recurring["agreement_id"])
        store.record_recurring_payment(
            recurring["agreement_id"], {"txid": pay_tx.txid(), "amount_sats": amount_to_sats("1")}
        )
        report.check(
            "14. Create recurring agreement",
            recurring_invoice["agreement_id"] == recurring["agreement_id"],
            recurring["agreement_id"],
        )

        escrow = store.create_escrow(
            chain,
            {
                "buyer_pubkey": customer.public_key_hex,
                "seller_pubkey": seller.public_key_hex,
                "mediator_pubkey": mediator.public_key_hex,
                "buyer_address": customer.address,
                "seller_address": seller.address,
                "mediator_address": mediator.address,
                "amount": "1",
                "terms": "QA escrow",
            }
        )
        escrow_fund_block = chain.mine_block(escrow["escrow_address"])
        qa_data = store.load()
        qa_data["escrows"][escrow["escrow_id"]]["funding_txid"] = escrow_fund_block.transactions[0].txid()
        store.save(qa_data)
        escrow = store.escrow_status(chain, escrow["escrow_id"])
        report.check("14b. Escrow chain-verified funding", escrow["status"] == "funded", escrow["escrow_id"])
        store.escrow_action(chain, escrow["escrow_id"], {"action": "release", "signer": "buyer", "to_address": seller.address})
        escrow_released = store.escrow_action(
            chain, escrow["escrow_id"], {"action": "release", "signer": "seller", "to_address": seller.address}
        )
        report.check(
            "15. Create escrow",
            escrow_released["status"] == "released" and escrow_released.get("payout_plan"),
            escrow["escrow_id"],
        )

        poll = store.create_poll({"title": "QA poll", "options": ["Yes", "No"], "creator_address": operator.address})
        option = poll["options"][0]["option_id"]
        message = store.poll_vote_message(poll["poll_id"], option)
        vote = store.cast_poll_vote(
            poll["poll_id"],
            {
                "voter_address": voter.address,
                "option_id": option,
                "signature": sign_message(voter.private_key, message),
            },
        )
        report.check("16. Create poll", vote["vote_count"] == 1 and vote["winner_option_id"] == option, poll["poll_id"])

        market = store.create_prediction_market(
            {"question": "Will QA pass?", "outcomes": ["YES", "NO"], "legal_acknowledged": True, "mode": "testnet_demo"}
        )
        yes_id = market["outcomes"][0]["outcome_id"]
        store.place_market_order(
            market["market_id"],
            {"address": trader_no.address, "outcome_id": yes_id, "side": "sell", "quantity": 3, "price_bps": 5000},
        )
        traded = store.place_market_order(
            market["market_id"],
            {"address": trader_yes.address, "outcome_id": yes_id, "side": "buy", "quantity": 3, "price_bps": 5000},
        )
        resolved = store.resolve_prediction_market(
            market["market_id"], {"winning_outcome_id": yes_id, "payout_per_share": "0.1"}
        )
        report.check(
            "17. Create prediction market in demo mode",
            traded["trades"] and resolved["status"] == "resolved",
            market["market_id"],
        )

        with webhook_capture() as (hook_url, received):
            store.register_webhook(
                {
                    "merchant_id": "qa-shop",
                    "url": hook_url,
                    "events": ["payment.confirmed"],
                    "secret": "qa-secret",
                    "backoff_seconds": 1,
                }
            )
            invoice2 = store.create_invoice(
                chain, {"address": merchant.address, "amount": "1", "merchant_id": "qa-shop"}
            )
            send_and_mine(chain, customer, merchant.address, "1")
            store.invoice_status(chain, invoice2["invoice_id"])
            delivered = store.deliver_webhook_events({"force": True, "timeout": 2})
            report.check(
                "18. Test webhook delivery",
                delivered["delivered"] >= 1
                and received
                and received[-1]["headers"].get("X-Netcoin-Signature", "").startswith("sha256="),
                f"delivered={delivered['delivered']}",
            )

        persisted = store.upsert_username({"username": "persistqa", "address": merchant.address})
        restarted = AppStore(chain.data_dir)
        report.check(
            "19. Restart server and confirm SQLite data persists",
            restarted.resolve_username("persistqa")["address"] == persisted["address"],
            str(restarted.sqlite_path),
        )

        os.environ["NETCOIN_APP_REQUIRE_ADMIN"] = "1"
        os.environ["NETCOIN_APP_ADMIN_TOKEN"] = "qa-admin-token"
        with Served(make_explorer_handler(chain)) as served:
            status_no_token, payload_no_token = http_json(f"{served.url}/api/admin/summary")
            status_with_token, payload_with_token = http_json(
                f"{served.url}/api/admin/summary", headers={"X-Netcoin-Admin-Token": "qa-admin-token"}
            )
        report.check(
            "20. Confirm admin routes reject requests without token",
            status_no_token == 401
            and status_with_token == 200
            and payload_with_token.get("node", {}).get("height", -1) >= 0,
            payload_no_token.get("error", ""),
        )

        status = store.security_status()
        report.check("Security status uses SQLite", status["storage_backend"] == "sqlite", status["storage_path"])
        return report
    finally:
        if old_storage is None:
            os.environ.pop("NETCOIN_APP_STORAGE", None)
        else:
            os.environ["NETCOIN_APP_STORAGE"] = old_storage
        if old_require_admin is None:
            os.environ.pop("NETCOIN_APP_REQUIRE_ADMIN", None)
        else:
            os.environ["NETCOIN_APP_REQUIRE_ADMIN"] = old_require_admin
        if old_admin_token is None:
            os.environ.pop("NETCOIN_APP_ADMIN_TOKEN", None)
        else:
            os.environ["NETCOIN_APP_ADMIN_TOKEN"] = old_admin_token
        if old_market_ack is None:
            os.environ.pop("NETCOIN_REQUIRE_MARKET_LEGAL_ACK", None)
        else:
            os.environ["NETCOIN_REQUIRE_MARKET_LEGAL_ACK"] = old_market_ack


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin local deployment QA checks")
    parser.add_argument("--data-dir", default="", help="optional directory to use instead of a temporary directory")
    parser.add_argument("--json", action="store_true", help="print JSON report")
    args = parser.parse_args()

    if args.data_dir:
        base = Path(args.data_dir)
        base.mkdir(parents=True, exist_ok=True)
        report = run_qa(base)
    else:
        with tempfile.TemporaryDirectory(prefix="netcoin-deployment-qa-") as tmp:
            report = run_qa(Path(tmp))

    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in payload["checks"]:
            mark = "PASS" if item["ok"] else "FAIL"
            detail = f" - {item['detail']}" if item.get("detail") else ""
            print(f"{mark}: {item['name']}{detail}")
        print(f"Result: {'PASS' if payload['ok'] else 'FAIL'} ({payload['count']} checks)")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
