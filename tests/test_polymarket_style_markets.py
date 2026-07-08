from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.professional_upgrade import validate_upgrade_manifest


def test_polymarket_style_market_order_ticker_and_orderbook(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market({
        "question": "Will the Polymarket-style Labs CLOB work?",
        "outcomes": ["YES", "NO"],
        "category": "Technology",
        "tags": ["netcoin", "markets"],
        "legal_acknowledged": True,
        "sandbox_short_mode": True,
    })
    mid = market["market_id"]
    yes = market["outcomes"][0]["outcome_id"]

    store.place_market_order(mid, {"trader": "demo:maker1", "demo_wallet": True, "side": "sell", "outcome_id": yes, "price_bps": 4500, "quantity": 2})
    seeded = store.place_market_order(mid, {"trader": "demo:maker2", "demo_wallet": True, "side": "sell", "outcome_id": yes, "price_bps": 4700, "quantity": 3})
    assert seeded["clob"]["books"][yes]["asks"][0]["price_bps"] == 4500
    assert seeded["clob"]["books"][yes]["ask_depth_shares"] == 5

    traded = store.place_market_order(mid, {
        "trader": "demo:taker",
        "demo_wallet": True,
        "side": "buy",
        "outcome_id": yes,
        "order_type": "market",
        "quantity": 3,
    })
    taker_order = traded["orders"][-1]
    assert taker_order["order_type"] == "market"
    assert taker_order["time_in_force"] == "IOC"
    assert taker_order["status"] == "filled"
    assert traded["stats"]["trade_count"] == 2
    assert traded["ticker"]["outcomes"][0]["last_price_bps"] == 4700

    book = store.market_orderbook(mid)
    assert book["type"] == "central_limit_order_book"
    assert book["books"][yes]["best_ask_bps"] == 4700
    assert book["books"][yes]["ask_depth_shares"] == 2

    positions = store.market_positions(mid, "demo:taker")
    assert positions["portfolios"][0]["positions"][0]["quantity"] == 3
    assert "equity_sats" in positions["portfolios"][0]


def test_fok_and_post_only_market_guards(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market({"question": "Will FOK guards work?", "outcomes": ["YES", "NO"], "legal_acknowledged": True})
    mid = market["market_id"]
    yes = market["outcomes"][0]["outcome_id"]
    store.place_market_order(mid, {"trader": "demo:maker", "demo_wallet": True, "side": "sell", "outcome_id": yes, "price_bps": 5000, "quantity": 1})
    with pytest.raises(AppError, match="FOK"):
        store.place_market_order(mid, {"trader": "demo:taker", "demo_wallet": True, "side": "buy", "outcome_id": yes, "order_type": "fok", "price_bps": 5000, "quantity": 2})
    with pytest.raises(AppError, match="post_only"):
        store.place_market_order(mid, {"trader": "demo:poster", "demo_wallet": True, "side": "buy", "outcome_id": yes, "price_bps": 5000, "quantity": 1, "post_only": True})


def test_professional_upgrade_manifest_is_valid():
    report = validate_upgrade_manifest(Path(__file__).resolve().parents[1])
    assert report["ok"] is True
    assert report["workstream_count"] >= 15
    assert report["production_claim"] is False
