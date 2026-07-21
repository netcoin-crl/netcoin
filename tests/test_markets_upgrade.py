from pathlib import Path

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def test_markets_have_order_ids_cancellation_wallets_and_stats(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    buyer = Wallet.create()
    seller = Wallet.create()
    store = AppStore(chain.data_dir)

    market = store.create_prediction_market(
        {
            "question": "Will enhanced markets pass tests?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "sandbox_short_mode": True,
        }
    )
    yes = market["outcomes"][0]["outcome_id"]

    resting = store.place_market_order(
        market["market_id"],
        {
            "trader_address": seller.address,
            "outcome_id": yes,
            "side": "sell",
            "quantity": 5,
            "price_bps": 4500,
        },
    )
    sell_order = next(o for o in resting["orders"] if o["side"] == "sell")
    assert sell_order["order_id"].startswith("ord_")
    assert resting["orderbook"][yes]["best_ask_bps"] == 4500
    assert resting["wallets"][seller.address]["reserved_sats"] > 0

    matched = store.place_market_order(
        market["market_id"],
        {
            "trader_address": buyer.address,
            "outcome_id": yes,
            "side": "buy",
            "quantity": 3,
            "price_bps": 5000,
        },
    )
    assert matched["trades"][0]["maker_order_id"] == sell_order["order_id"]
    assert matched["trades"][0]["taker"] == buyer.address
    assert matched["stats"]["volume_shares"] == 3
    assert matched["stats"]["last_trade"]["price_bps"] == 4500
    assert matched["positions"][buyer.address][yes] == 3

    remaining_sell = next(o for o in matched["orders"] if o["order_id"] == sell_order["order_id"])
    assert remaining_sell["remaining"] == 2
    canceled = store.cancel_market_order(
        market["market_id"], sell_order["order_id"], {"trader_address": seller.address}
    )
    canceled_order = next(o for o in canceled["orders"] if o["order_id"] == sell_order["order_id"])
    assert canceled_order["status"] == "canceled"
    assert canceled["orderbook"][yes]["sells"] == []


def test_unused_market_can_be_deleted_but_active_market_cannot(tmp_path: Path):
    store = AppStore(tmp_path)
    unused = store.create_prediction_market({"question": "Delete me", "outcomes": ["YES", "NO"]})
    assert store.delete_prediction_market(unused["market_id"])["deleted"] is True
    try:
        store.prediction_market(unused["market_id"])
        assert False, "expected deleted market to be absent"
    except AppError as exc:
        assert "not found" in str(exc)

    active = store.create_prediction_market({"question": "Keep me", "outcomes": ["YES", "NO"]})
    store.place_market_order(active["market_id"], {"trader": "demo:alice", "demo_wallet": True, "outcome_id": "out1", "quantity": 1, "price_bps": 5000})
    try:
        store.delete_prediction_market(active["market_id"])
        assert False, "expected active market deletion to be rejected"
    except AppError as exc:
        assert "without orders" in str(exc)


def test_markets_can_block_unbacked_sells_when_short_mode_disabled(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    trader = Wallet.create()
    store = AppStore(chain.data_dir)
    market = store.create_prediction_market(
        {
            "question": "Will short checks work?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "sandbox_short_mode": False,
        }
    )
    yes = market["outcomes"][0]["outcome_id"]
    try:
        store.place_market_order(
            market["market_id"],
            {
                "trader_address": trader.address,
                "outcome_id": yes,
                "side": "sell",
                "quantity": 1,
                "price_bps": 4000,
            },
        )
        assert False, "expected short-mode rejection"
    except AppError as exc:
        assert "sandbox_short_mode" in str(exc)


def test_demo_traders_resolve_to_demo_payouts_not_chain_outputs(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    market = store.create_prediction_market(
        {"question": "Demo trader market?", "outcomes": ["YES", "NO"], "legal_acknowledged": True}
    )
    yes = market["outcomes"][0]["outcome_id"]
    store.place_market_order(
        market["market_id"],
        {
            "trader_address": "demo:bob",
            "allow_unverified_demo": True,
            "outcome_id": yes,
            "side": "sell",
            "quantity": 2,
            "price_bps": 4000,
        },
    )
    store.place_market_order(
        market["market_id"],
        {
            "trader_address": "demo:alice",
            "allow_unverified_demo": True,
            "outcome_id": yes,
            "side": "buy",
            "quantity": 2,
            "price_bps": 5000,
        },
    )
    resolved = store.resolve_prediction_market(
        market["market_id"], {"winning_outcome_id": yes, "payout_per_share": "1"}
    )
    assert resolved["status"] == "resolved"
    assert resolved["demo_payouts"][0]["trader_id"] == "demo:alice"
    assert resolved["payout_plan"]["outputs"] == []
