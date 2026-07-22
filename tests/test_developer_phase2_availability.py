from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore, route_app_get, route_app_post
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def test_developer_api_keys_are_available_and_revocable(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)

    status, created = route_app_post(
        store,
        chain,
        "/api/developer/api-keys",
        {"developer_id": "game-studio"},
    )
    assert status == 200
    assert created["merchant_id"] == "game-studio"
    assert created["api_key"].startswith("nck_")
    assert store.check_api_key(created["api_key"])

    # Without proving you hold an active key for this account, listing must not
    # leak the revokable key_id (it's a public developer_id, not a secret).
    anon_status, anon_listed, _ = route_app_get(store, chain, "/api/developer/api-keys", {"developer_id": ["game-studio"]})
    assert anon_status == 200
    assert anon_listed["count"] == 1
    assert "key_id" not in anon_listed["api_keys"][0]

    get_status, listed, _ = route_app_get(
        store,
        chain,
        "/api/developer/api-keys",
        {"developer_id": ["game-studio"], "_presented_api_key": [created["api_key"]]},
    )
    assert get_status == 200
    assert listed["count"] == 1
    assert listed["api_keys"][0]["key_id"] == created["key_id"]
    assert "key_hash" not in listed["api_keys"][0]
    assert "api_key" not in listed["api_keys"][0]
    assert "owner_address" not in listed["api_keys"][0]
    assert listed["api_keys"][0]["active"] is True

    # Revoking without a wallet signature requires proving possession of a
    # currently-active key for this same account -- key_id alone is not enough.
    revoke_status, revoked = route_app_post(
        store,
        chain,
        "/api/developer/api-keys/revoke",
        {"developer_id": "game-studio", "key_id": created["key_id"], "api_key": created["api_key"]},
    )
    assert revoke_status == 200
    assert revoked["active"] is False
    assert not store.check_api_key(created["api_key"])


def test_api_key_cannot_be_enumerated_or_revoked_by_an_unrelated_caller(tmp_path: Path):
    """Regression: knowing a public developer_id + a listed key_id used to be
    enough to revoke someone else's key with zero authentication."""
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    _, created = route_app_post(store, chain, "/api/developer/api-keys", {"developer_id": "victim"})

    # An unrelated caller who only knows the (public) developer_id cannot see key_id.
    _, listed, _ = route_app_get(store, chain, "/api/developer/api-keys", {"developer_id": ["victim"]})
    assert "key_id" not in listed["api_keys"][0]

    # And cannot revoke it even if they somehow learn the key_id another way.
    with pytest.raises(AppError, match="valid API key"):
        route_app_post(
            store,
            chain,
            "/api/developer/api-keys/revoke",
            {"developer_id": "victim", "key_id": created["key_id"]},
        )
    assert store.check_api_key(created["api_key"])


@pytest.mark.parametrize(
    "path,body,expected_key",
    [
        (
            "/api/developer/payment-links",
            {"developer_id": "game-studio", "address": None, "amount": "0.25", "title": "Starter pack"},
            "checkout_url",
        ),
        (
            "/api/developer/simulate/rewards",
            {"developer_id": "game-studio", "count": 10, "amount_sats": 50},
            "recommendation",
        ),
    ],
)
def test_developer_console_write_surfaces_use_real_endpoints(tmp_path: Path, path: str, body: dict, expected_key: str):
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    if body.get("address") is None:
        body["address"] = recipient.address
    store = AppStore(chain.data_dir)

    status, result = route_app_post(store, chain, path, body)
    assert status == 200
    assert expected_key in result


def test_developer_webhook_registration_is_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", "1")
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)

    status, hook = route_app_post(
        store,
        chain,
        "/api/developer/webhooks",
        {
            "developer_id": "game-studio",
            "url": "http://127.0.0.1:9/hook",
            "events": ["payment.confirmed", "reward.created"],
        },
    )
    assert status == 200
    assert hook["merchant_id"] == "game-studio"
    assert hook["secret"]

    get_status, listing, _ = route_app_get(store, chain, "/api/developer/webhooks", {"developer_id": ["game-studio"]})
    assert get_status == 200
    assert len(listing["webhooks"]) == 1


def test_developer_api_key_revoke_requires_owner(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    _, created = route_app_post(store, chain, "/api/developer/api-keys", {"developer_id": "game-studio"})

    with pytest.raises(AppError, match="does not belong"):
        route_app_post(
            store,
            chain,
            "/api/developer/api-keys/revoke",
            {"developer_id": "other-studio", "key_id": created["key_id"]},
        )
