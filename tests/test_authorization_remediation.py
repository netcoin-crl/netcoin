import time
from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore, route_app_get, route_app_post
from netcoin.apps.auth import SignedEnvelope, canonical_body_hash
from netcoin.chain import Blockchain
from netcoin.crypto import sign_message
from netcoin.wallet import Wallet


def signed_http(payload: dict, wallet: Wallet, path: str, *, operator: bool = False) -> dict:
    body = dict(payload)
    body["__netcoin_http_request"] = True
    if operator:
        body["__netcoin_operator_verified"] = True
    envelope = SignedEnvelope(
        address=wallet.segwit_address,
        method="POST",
        path=path,
        body_hash=canonical_body_hash(body),
        timestamp=int(time.time()),
        nonce=f"test-{time.time_ns()}",
        signature="",
    )
    body["signed_envelope"] = {
        "address": envelope.address,
        "method": envelope.method,
        "path": envelope.path,
        "body_hash": envelope.body_hash,
        "timestamp": envelope.timestamp,
        "nonce": envelope.nonce,
        "signature": sign_message(wallet.private_key, envelope.message()),
    }
    return body


def test_token_http_actor_cannot_impersonate_creator(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    alice = Wallet.create()
    bob = Wallet.create()

    with pytest.raises(AppError, match="signed wallet must match creator"):
        route_app_post(
            store,
            chain,
            "/api/tokens",
            signed_http({"symbol": "SAFE", "creator": bob.segwit_address}, alice, "/tokens"),
        )


def test_team_wallet_requires_verified_member(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    alice = Wallet.create()
    bob = Wallet.create()
    _, team = route_app_post(
        store,
        chain,
        "/api/wallet/team-wallets",
        signed_http({"name": "Ops", "members": [alice.segwit_address]}, alice, "/wallet/team-wallets"),
    )

    path = f"/wallet/team-wallets/{team['wallet_id']}/proposals"
    with pytest.raises(AppError, match="only a team-wallet member"):
        route_app_post(
            store,
            chain,
            "/api" + path,
            signed_http({"to_address": alice.segwit_address, "amount_sats": 1}, bob, path),
        )


def test_poll_envelope_binds_voter_and_ignores_client_weight(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    alice = Wallet.create()
    bob = Wallet.create()
    _, poll = route_app_post(
        store,
        chain,
        "/api/polls",
        signed_http(
            {"title": "Ship it?", "options": ["Yes", "No"], "creator_address": alice.segwit_address},
            alice,
            "/polls",
        ),
    )
    option = poll["options"][0]["option_id"]
    path = f"/polls/{poll['poll_id']}/vote"
    _, result = route_app_post(
        store,
        chain,
        "/api" + path,
        signed_http({"voter_address": alice.segwit_address, "option_id": option, "weight": 999}, alice, path),
    )
    assert result["results"][option]["weight"] == 1

    with pytest.raises(AppError, match="signed wallet must match voter_address"):
        route_app_post(
            store,
            chain,
            "/api" + path,
            signed_http({"voter_address": alice.segwit_address, "option_id": option}, bob, path),
        )


def test_webhook_reads_never_return_signing_secret(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    created = store.register_webhook({"merchant_id": "demo", "url": "https://example.com/hook"})
    assert created["secret"]

    _, result, _ = route_app_get(store, chain, "/api/merchant/webhooks", {})
    assert result["webhooks"]
    assert "secret" not in result["webhooks"][0]
    assert "secret_hash" not in result["webhooks"][0]


def test_exchange_approvals_use_two_verified_wallets(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    alice = Wallet.create()
    bob = Wallet.create()
    withdrawal = store.request_exchange_withdrawal(
        {"customer_id": "customer", "amount_sats": 10, "to_address": alice.segwit_address}
    )
    path = f"/exchange/withdrawals/{withdrawal['withdrawal_id']}/approve"

    _, first = route_app_post(
        store, chain, "/api" + path, signed_http({"approver": "fake-a"}, alice, path, operator=True)
    )
    assert first["status"] == "approved"
    _, second = route_app_post(
        store, chain, "/api" + path, signed_http({"approver": "fake-b"}, bob, path, operator=True)
    )
    assert second["status"] == "released"
    approvals = store.load()["exchange_withdrawal_approvals"]
    assert {item["approver"] for item in approvals} == {alice.segwit_address, bob.segwit_address}


def test_escrow_action_requires_a_real_signature_from_the_claimed_participant(tmp_path: Path):
    """Regression: an unsigned HTTP request could release/refund an escrow by
    simply naming a participant address in `signer`, with no proof at all."""
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    buyer, seller, mediator = Wallet.create(), Wallet.create(), Wallet.create()
    attacker = Wallet.create()
    escrow = store.create_escrow(
        {
            "buyer_pubkey": buyer.public_key.hex(),
            "seller_pubkey": seller.public_key.hex(),
            "mediator_pubkey": mediator.public_key.hex(),
            "buyer_address": buyer.segwit_address,
            "seller_address": seller.segwit_address,
            "amount_sats": 1_000_000,
        }
    )
    escrow_id = escrow["escrow_id"]

    # No signature at all, HTTP request, claiming to be the buyer -- must fail.
    with pytest.raises(AppError, match="valid signature"):
        store.escrow_action(
            escrow_id,
            {"action": "release", "signer": buyer.segwit_address, "__netcoin_http_request": True},
        )

    # A signature from a wallet that ISN'T the claimed participant must also fail.
    bad_message = f"NetCoin escrow action\nescrow-action-v1\n{escrow_id}\nrelease\n{buyer.segwit_address}"
    bad_signature = sign_message(attacker.private_key, bad_message)
    with pytest.raises(AppError, match="valid signature"):
        store.escrow_action(
            escrow_id,
            {
                "action": "release",
                "signer": buyer.segwit_address,
                "signature": bad_signature,
                "__netcoin_http_request": True,
            },
        )

    # The real buyer's own signature over the exact message is accepted.
    good_message = f"NetCoin escrow action\nescrow-action-v1\n{escrow_id}\nrelease\n{buyer.segwit_address}"
    good_signature = sign_message(buyer.private_key, good_message)
    result = store.escrow_action(
        escrow_id,
        {
            "action": "release",
            "signer": buyer.segwit_address,
            "signature": good_signature,
            "__netcoin_http_request": True,
        },
    )
    assert result["status"] == "pending_release"


def test_bounty_cannot_be_awarded_by_a_non_sponsor_http_caller(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    sponsor, attacker = Wallet.create(), Wallet.create()

    bounty = store.create_bounty({"title": "Fix a bug", "sponsor_address": sponsor.segwit_address})
    path = "/community/bounties/" + bounty["bounty_id"] + "/award"
    with pytest.raises(AppError, match="only the bounty sponsor"):
        route_app_post(
            store,
            chain,
            "/api" + path,
            signed_http({"winner_address": attacker.segwit_address}, attacker, path),
        )
    assert store.load()["bounties"][bounty["bounty_id"]]["status"] == "open"

    # No signature at all must also be rejected, not silently allowed through.
    with pytest.raises(AppError, match="verified wallet signature"):
        route_app_post(store, chain, "/api" + path, {"winner_address": attacker.segwit_address, "__netcoin_http_request": True})


def test_poll_cannot_be_closed_early_by_a_non_creator_http_caller(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    creator, attacker = Wallet.create(), Wallet.create()

    poll = store.create_poll({"title": "Ship it?", "options": ["Yes", "No"], "creator_address": creator.segwit_address})
    path = "/polls/" + poll["poll_id"] + "/close"
    with pytest.raises(AppError, match="only the poll creator"):
        route_app_post(store, chain, "/api" + path, signed_http({}, attacker, path))
    assert store.load()["polls"][poll["poll_id"]]["status"] == "open"

    with pytest.raises(AppError, match="verified wallet signature"):
        route_app_post(store, chain, "/api" + path, {"__netcoin_http_request": True})
