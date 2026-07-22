from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore


def _market(store: AppStore, **overrides):
    payload = {"question": "Will it rain?", "outcomes": ["YES", "NO"], "creator_address": "creator"}
    payload.update(overrides)
    return store.create_prediction_market(payload)


def test_restricted_topic_operator_override_rejected_on_http_request(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    with pytest.raises(AppError):
        _market(
            store,
            question="Who wins the election?",
            operator_override=True,
            __netcoin_http_request=True,
        )


def test_restricted_topic_operator_override_allowed_on_direct_call(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    market = _market(store, question="Who wins the election?", operator_override=True)
    assert market["market_id"]


def test_per_order_allow_subtick_ignored_on_http_request(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    market = _market(store)
    with pytest.raises(AppError, match="min_tick_bps"):
        store.place_market_order(
            market["market_id"],
            {
                "trader_address": "demo:trader",
                "outcome_id": market["outcomes"][0]["outcome_id"],
                "side": "buy",
                "quantity": 1,
                "price_bps": 5001,
                "allow_subtick": True,
                "__netcoin_http_request": True,
            },
        )


def test_per_order_sandbox_short_mode_cannot_override_disabled_market(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    market = _market(store, sandbox_short_mode=False)
    with pytest.raises(AppError, match="sandbox_short_mode"):
        store.place_market_order(
            market["market_id"],
            {
                "trader_address": "demo:shorter",
                "outcome_id": market["outcomes"][0]["outcome_id"],
                "side": "sell",
                "quantity": 1,
                "price_bps": 5000,
                "sandbox_short_mode": True,
            },
        )


def test_trader_with_position_can_dispute_resolution(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    market = _market(store)
    market_id = market["market_id"]
    outcome_yes = market["outcomes"][0]["outcome_id"]
    store.place_market_order(
        market_id,
        {"trader_address": "demo:trader", "outcome_id": outcome_yes, "side": "buy", "quantity": 1, "price_bps": 5000},
    )
    data = store.load()
    data["prediction_markets"][market_id]["positions"]["demo:trader"] = {outcome_yes: 1}
    store.save(data)
    disputed = store.dispute_market_resolution(
        market_id, {"reason": "bad resolution", "trader_address": "demo:trader"}
    )
    assert disputed["resolution_workflow"]["status"] == "disputed"
