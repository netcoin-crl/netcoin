from pathlib import Path

from netcoin.apps import AppError, AppStore


def test_reset_revokes_keys_and_deactivates_webhooks_for_that_developer_only(tmp_path: Path):
    store = AppStore(tmp_path)
    store.create_api_key({"merchant_id": "studio-a"})
    store.create_api_key({"merchant_id": "studio-a"})
    store.create_api_key({"merchant_id": "studio-b"})
    store.register_webhook({"merchant_id": "studio-a", "url": "https://example.com/hook"})
    store.register_webhook({"merchant_id": "studio-b", "url": "https://example.com/hook"})

    result = store.reset_developer_sandbox("studio-a")
    assert result["revoked_keys"] == 2
    assert result["deactivated_webhooks"] == 1

    data = store.load()
    studio_a_keys = [k for k in data["api_keys"].values() if k["merchant_id"] == "studio-a"]
    studio_b_keys = [k for k in data["api_keys"].values() if k["merchant_id"] == "studio-b"]
    assert all(not k["active"] for k in studio_a_keys)
    assert all(k["active"] for k in studio_b_keys)

    studio_a_hooks = [h for h in data["webhooks"].values() if h["merchant_id"] == "studio-a"]
    studio_b_hooks = [h for h in data["webhooks"].values() if h["merchant_id"] == "studio-b"]
    assert all(not h["active"] for h in studio_a_hooks)
    assert all(h["active"] for h in studio_b_hooks)


def test_reset_does_not_touch_payment_links_or_invoices(tmp_path: Path):
    store = AppStore(tmp_path)
    from netcoin.chain import Blockchain
    from netcoin.wallet import Wallet

    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    link = store.create_payment_link(chain, {"developer_id": "studio-a", "address": wallet.segwit_address, "amount": "1.0"})

    store.reset_developer_sandbox("studio-a")

    data = store.load()
    assert link["link_id"] in data["payment_links"]
    assert link["invoice_id"] in data["invoices"]


def test_reset_requires_a_developer_id(tmp_path: Path):
    import pytest

    store = AppStore(tmp_path)
    with pytest.raises(AppError, match="developer_id is required"):
        store.reset_developer_sandbox("")
