from pathlib import Path

from netcoin.apps import AppStore


def test_market_surveillance_flags_concentration_and_disputes(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Will the demo event happen?",
            "outcomes": ["YES", "NO"],
            "mode": "play_money",
            "concentration_bps": 4000,
            "allow_unverified_demo": True,
        }
    )
    mid = market["market_id"]
    # Maker sell first, then buyer crosses it.
    store.place_market_order(
        mid,
        {
            "trader": "demo:bob",
            "demo_wallet": True,
            "side": "sell",
            "outcome_id": "out1",
            "price_bps": 5000,
            "quantity": 10,
        },
    )
    traded = store.place_market_order(
        mid,
        {
            "trader": "demo:alice",
            "demo_wallet": True,
            "side": "buy",
            "outcome_id": "out1",
            "price_bps": 5000,
            "quantity": 10,
        },
    )
    alerts = traded["surveillance"]["alerts"]
    assert any(a["code"] == "volume_concentration" for a in alerts)
    disputed = store.dispute_market_resolution(
        mid, {"actor": "alice", "reason": "source is ambiguous", "evidence_url": "https://example.com/evidence"}
    )
    assert disputed["resolution_workflow"]["status"] == "disputed"
    assert any(a["code"] == "active_resolution_disputes" for a in disputed["surveillance"]["alerts"])
    all_reports = store.market_surveillance()
    assert all_reports["alert_count"] >= 1


def test_market_surveillance_route_for_single_market(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market({"question": "Demo?", "outcomes": ["YES", "NO"], "mode": "testnet_demo"})
    report = store.market_surveillance(market["market_id"])
    assert report["market_id"] == market["market_id"]
    assert "surveillance" in report
