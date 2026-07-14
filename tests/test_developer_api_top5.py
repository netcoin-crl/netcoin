from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore, route_app_get, route_app_post
from netcoin.chain import Blockchain
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def test_developer_api_top_five_app_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", "1")
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    store = AppStore(chain.data_dir)

    link_status, link = route_app_post(
        store,
        chain,
        "/api/developer/payment-links",
        {
            "developer_id": "game-studio",
            "address": recipient.address,
            "amount": "0.25",
            "title": "Starter pack",
        },
    )
    assert link_status == 200
    assert link["developer_id"] == "game-studio"
    assert link["invoice"]["merchant_id"] == "game-studio"
    assert link["checkout_url"].startswith("/pay/")

    reward_status, reward = route_app_post(
        store,
        chain,
        "/api/developer/rewards",
        {
            "developer_id": "game-studio",
            "player_id": "player-7",
            "address": recipient.address,
            "amount_sats": 2_500,
            "event": "daily_quest",
            "idempotency_key": "daily-quest-player-7-1",
        },
    )
    assert reward_status == 200
    assert reward["amount_sats"] == 2_500
    assert reward["payout_plan"]["kind"] == "reward"

    replay_status, replay = route_app_post(
        store,
        chain,
        "/api/developer/rewards",
        {
            "developer_id": "game-studio",
            "player_id": "player-7",
            "address": recipient.address,
            "amount_sats": 2_500,
            "event": "daily_quest",
            "idempotency_key": "daily-quest-player-7-1",
        },
    )
    assert replay_status == 200
    assert replay["idempotent_replay"] is True
    assert replay["reward_id"] == reward["reward_id"]

    with pytest.raises(AppError, match="different request body"):
        route_app_post(
            store,
            chain,
            "/api/developer/rewards",
            {
                "developer_id": "game-studio",
                "player_id": "player-7",
                "address": recipient.address,
                "amount_sats": 3_000,
                "event": "daily_quest",
                "idempotency_key": "daily-quest-player-7-1",
            },
        )

    withdrawal_status, withdrawal = route_app_post(
        store,
        chain,
        "/api/developer/withdrawals",
        {
            "developer_id": "game-studio",
            "player_id": "player-7",
            "address": recipient.address,
            "amount": "0.01",
            "reason": "player withdrawal threshold",
        },
    )
    assert withdrawal_status == 200
    assert withdrawal["amount_sats"] == amount_to_sats("0.01")
    assert withdrawal["payout_plan"]["kind"] == "developer_withdrawal"

    hook_status, hook = route_app_post(
        store,
        chain,
        "/api/developer/webhooks",
        {
            "developer_id": "game-studio",
            "url": "http://127.0.0.1:9/hook",
            "events": ["reward.created", "withdrawal.created"],
            "secret": "test-secret",
        },
    )
    assert hook_status == 200
    assert hook["merchant_id"] == "game-studio"

    dash_status, dashboard, ctype = route_app_get(
        store, chain, "/api/developer/dashboard", {"developer_id": ["game-studio"]}
    )
    assert dash_status == 200
    assert ctype == "application/json"
    assert dashboard["schema"] == "netcoin-developer-dashboard-v1"
    assert dashboard["counts"]["rewards"] == 1
    assert dashboard["counts"]["withdrawals"] == 1
    assert dashboard["counts"]["payment_links"] == 1
    assert dashboard["counts"]["webhooks"] == 1
    assert dashboard["totals"]["reward_sats"] == 2_500


def test_developer_api_next_seven_features(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", "1")
    chain = Blockchain(tmp_path / "chain")
    funder = Wallet.create()
    player = Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)
    store = AppStore(chain.data_dir)

    sdk_status, sdk, _ = route_app_get(store, chain, "/api/developer/sdk", {})
    verifier_status, verifiers, _ = route_app_get(store, chain, "/api/developer/webhook-verifiers", {})
    assert sdk_status == 200
    assert verifier_status == 200
    assert "@netcoin/developer" in {p["package"] for p in sdk["packages"]}
    assert verifiers["algorithm"] == "HMAC-SHA256 over the raw JSON request body"

    watch_status, watch = route_app_post(
        store,
        chain,
        "/api/developer/watch-addresses",
        {"developer_id": "game-studio", "address": player.address, "label": "player deposit"},
    )
    assert watch_status == 200
    assert watch["address"] == player.address

    deposit_tx = funder.create_transaction(chain, player.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(deposit_tx)
    chain.mine_block(funder.address)
    deposits_status, deposits, _ = route_app_get(
        store, chain, "/api/developer/deposits", {"developer_id": ["game-studio"]}
    )
    assert deposits_status == 200
    assert any(row["txid"] == deposit_tx.txid() and row["ready"] for row in deposits["deposits"])

    unsigned_status, unsigned = route_app_post(
        store,
        chain,
        "/api/developer/transactions/build",
        {
            "from_address": funder.address,
            "to_address": player.address,
            "amount": "0.2",
            "fee": "0.01",
        },
    )
    assert unsigned_status == 200
    assert unsigned["unsigned"] is True
    assert unsigned["transaction"]["inputs"]
    assert unsigned["transaction"]["outputs"]

    batch_status, batch = route_app_post(
        store,
        chain,
        "/api/developer/rewards/batch",
        {
            "developer_id": "game-studio",
            "reason": "tournament",
            "rewards": [
                {"player_id": "p1", "address": player.address, "amount_sats": 1000},
                {"player_id": "p2", "address": player.address, "amount_sats": 2000},
            ],
        },
    )
    assert batch_status == 200
    assert batch["reward_count"] == 2
    assert batch["total_sats"] == 3000
    assert batch["payout_plan"]["kind"] == "batch_reward"

    sim_status, sim = route_app_post(
        store,
        chain,
        "/api/developer/simulate/rewards",
        {"developer_id": "game-studio", "count": 10, "amount_sats": 50},
    )
    assert sim_status == 200
    assert sim["reward_count"] == 10
    assert sim["dust_risk"] is True
    assert "off-chain" in sim["recommendation"]

    console_status, console, _ = route_app_get(
        store, chain, "/api/developer/console", {"developer_id": ["game-studio"]}
    )
    assert console_status == 200
    assert "build_unsigned_transaction" in console["quick_actions"]
    assert console["dashboard"]["counts"]["rewards"] == 2
