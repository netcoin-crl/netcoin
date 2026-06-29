import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.apps import AppStore
from netcoin.chain import Blockchain
from netcoin.explorer_server import make_handler
from netcoin.wallet import Wallet


class Served:
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


def get_json(url: str, headers: dict | None = None):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())


def post_json(url: str, payload: dict, headers: dict | None = None):
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())


def test_admin_payout_plan_lifecycle(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    store = AppStore(chain.data_dir)
    reward = store.create_reward({"address": wallet.address, "amount": "0.5", "reason": "operator test"})
    payout_id = reward["payout_plan"]["payout_id"]

    listed = store.list_payout_plans()
    assert listed["count"] == 1
    assert listed["payout_plans"][0]["payout_id"] == payout_id
    assert listed["payout_plans"][0]["status"] == "pending_operator_review"

    reviewed = store.review_payout_plan(payout_id, {"reviewer": "alice", "notes": "looks correct"})
    assert reviewed["status"] == "ready_for_wallet_signing"
    assert reviewed["reviewed_by"] == "alice"

    bundle = store.payout_signer_bundle(payout_id)
    assert bundle["wallet_import"]["outputs"][0]["address"] == wallet.address
    assert "operator_checklist" in bundle

    signed = store.record_signed_payout(payout_id, {"txid": "abc123", "signer": "offline1"})
    assert signed["status"] == "signed_ready_to_broadcast"
    assert signed["signed_txid"] == "abc123"

    broadcasted = store.record_broadcasted_payout(payout_id, {"txid": "deadbeef", "operator": "bob"})
    assert broadcasted["status"] == "broadcast_recorded"
    assert broadcasted["broadcast_txid"] == "deadbeef"
    assert store.admin_summary(chain)["counts"]["payout_plans"] == 1


def test_admin_api_gate_and_dashboard_page(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NETCOIN_APP_REQUIRE_ADMIN", "1")
    monkeypatch.setenv("NETCOIN_APP_ADMIN_TOKEN", "secret")
    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    store = AppStore(chain.data_dir)
    store.create_reward({"address": wallet.address, "amount": "0.2", "reason": "admin api"})

    with Served(chain) as srv:
        # Public operator landing page exists, but sensitive JSON requires the admin token.
        with urlopen(f"{srv.url}/admin", timeout=5) as response:
            html = response.read().decode()
        assert "Admin Operator Dashboard" in html

        try:
            get_json(f"{srv.url}/api/admin/summary")
            assert False, "expected admin token failure"
        except HTTPError as exc:
            assert exc.code == 401

        headers = {"X-Netcoin-Admin-Token": "secret"}
        summary = get_json(f"{srv.url}/api/admin/summary", headers=headers)
        payouts = get_json(f"{srv.url}/api/admin/payouts", headers=headers)
        payout_id = payouts["payout_plans"][0]["payout_id"]
        approved = post_json(f"{srv.url}/api/admin/payouts/{payout_id}/review", {"reviewer": "admin"}, headers=headers)
        bundle = get_json(f"{srv.url}/api/admin/payouts/{payout_id}/bundle", headers=headers)

    assert summary["counts"]["payout_plans"] == 1
    assert approved["status"] == "ready_for_wallet_signing"
    assert bundle["payout_plan"]["payout_id"] == payout_id


def test_admin_static_assets_exist_and_pass_basic_content_check():
    admin_html = Path("webexplorer/public/admin.html").read_text()
    admin_js = Path("webexplorer/public/admin-app.js").read_text()
    assert "NetCoin Admin Operator Dashboard" in admin_html
    assert "/admin/summary" in admin_js
    assert "/admin/payouts" in admin_js
    assert "X-Netcoin-Admin-Token" in admin_js


def test_team_wallet_payout_plan_appears_in_admin_lifecycle(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    member = Wallet.create()
    store = AppStore(chain.data_dir)
    team = store.create_team_wallet({"name": "Ops", "required_approvals": 1, "members": ["alice"]})
    proposal = store.create_team_proposal(
        team["wallet_id"],
        {"created_by": "alice", "to_address": member.address, "amount": "0.25", "memo": "team payout"},
    )
    payout_id = proposal["payout_plan"]["payout_id"]

    listed = store.list_payout_plans()
    assert any(row["payout_id"] == payout_id and row["source_type"] == "team_wallet" for row in listed["payout_plans"])

    reviewed = store.review_payout_plan(payout_id, {"reviewer": "operator"})
    assert reviewed["status"] == "ready_for_wallet_signing"

    signed = store.record_signed_payout(payout_id, {"txid": "team-signed"})
    assert signed["status"] == "signed_ready_to_broadcast"

    broadcasted = store.record_broadcasted_payout(payout_id, {"txid": "team-broadcast"})
    assert broadcasted["status"] == "broadcast_recorded"
