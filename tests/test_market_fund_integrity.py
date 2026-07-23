from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore


def _market(store: AppStore, **overrides):
    payload = {"question": "Will it rain?", "outcomes": ["YES", "NO"], "creator_address": "creator"}
    payload.update(overrides)
    return store.create_prediction_market(payload)


def test_demo_wallet_balance_ignores_caller_supplied_initial_balance(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    market = _market(store)
    store.place_market_order(
        market["market_id"],
        {
            "trader_address": "demo:attacker",
            "outcome_id": market["outcomes"][0]["outcome_id"],
            "side": "buy",
            "quantity": 1,
            "price_bps": 5000,
            "initial_balance_sats": 10**15,
            "demo_balance_sats": 10**15,
        },
    )
    refreshed = store.prediction_market(market["market_id"])
    wallet = refreshed["wallets"]["demo:attacker"]
    assert wallet["total_deposited_sats"] < 10**15


def test_market_id_collision_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    _market(store, market_id="fixed-id")
    with pytest.raises(AppError, match="already exists"):
        _market(store, market_id="fixed-id", question="a different question entirely", allow_duplicate=True)


def test_resolution_payout_cannot_exceed_collateral_pool(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    market = _market(store)
    market_id = market["market_id"]
    outcome_yes = market["outcomes"][0]["outcome_id"]
    outcome_no = market["outcomes"][1]["outcome_id"]

    store.place_market_order(
        market_id,
        {"trader_address": "demo:buyer", "outcome_id": outcome_yes, "side": "buy", "quantity": 1, "price_bps": 5000},
    )
    store.place_market_order(
        market_id,
        {"trader_address": "demo:seller", "outcome_id": outcome_no, "side": "buy", "quantity": 1, "price_bps": 5000},
    )
    data = store.load()
    m = data["prediction_markets"][market_id]
    # Simulate more winning shares than the market's collateral pool can cover.
    m["positions"]["demo:buyer"] = {outcome_yes: 1_000_000}
    m["collateral_pool_sats"] = 100
    store.save(data)

    resolved = store.resolve_prediction_market(market_id, {"winning_outcome_id": outcome_yes, "creator_address": "creator"})
    payout_total = sum(p["amount_sats"] for p in resolved.get("demo_payouts", []))
    assert payout_total <= 100
