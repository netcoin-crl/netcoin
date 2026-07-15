import json
from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.professional_upgrade import validate_upgrade_manifest


class _FakeGammaResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *_args):
        return self._body


def _patch_gamma_api(monkeypatch, payload):
    import netcoin.apps.markets as markets_module

    def fake_urlopen(_req, timeout=6):
        return _FakeGammaResponse(payload)

    monkeypatch.setattr(markets_module.urllib.request, "urlopen", fake_urlopen)


def test_polymarket_style_market_order_ticker_and_orderbook(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Will the Polymarket-style Labs CLOB work?",
            "outcomes": ["YES", "NO"],
            "category": "Technology",
            "tags": ["netcoin", "markets"],
            "legal_acknowledged": True,
            "sandbox_short_mode": True,
        }
    )
    mid = market["market_id"]
    yes = market["outcomes"][0]["outcome_id"]

    store.place_market_order(
        mid,
        {
            "trader": "demo:maker1",
            "demo_wallet": True,
            "side": "sell",
            "outcome_id": yes,
            "price_bps": 4500,
            "quantity": 2,
        },
    )
    seeded = store.place_market_order(
        mid,
        {
            "trader": "demo:maker2",
            "demo_wallet": True,
            "side": "sell",
            "outcome_id": yes,
            "price_bps": 4700,
            "quantity": 3,
        },
    )
    assert seeded["clob"]["books"][yes]["asks"][0]["price_bps"] == 4500
    assert seeded["clob"]["books"][yes]["ask_depth_shares"] == 5

    traded = store.place_market_order(
        mid,
        {
            "trader": "demo:taker",
            "demo_wallet": True,
            "side": "buy",
            "outcome_id": yes,
            "order_type": "market",
            "quantity": 3,
        },
    )
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
    market = store.create_prediction_market(
        {"question": "Will FOK guards work?", "outcomes": ["YES", "NO"], "legal_acknowledged": True}
    )
    mid = market["market_id"]
    yes = market["outcomes"][0]["outcome_id"]
    store.place_market_order(
        mid,
        {
            "trader": "demo:maker",
            "demo_wallet": True,
            "side": "sell",
            "outcome_id": yes,
            "price_bps": 5000,
            "quantity": 1,
        },
    )
    with pytest.raises(AppError, match="FOK"):
        store.place_market_order(
            mid,
            {
                "trader": "demo:taker",
                "demo_wallet": True,
                "side": "buy",
                "outcome_id": yes,
                "order_type": "fok",
                "price_bps": 5000,
                "quantity": 2,
            },
        )
    with pytest.raises(AppError, match="post_only"):
        store.place_market_order(
            mid,
            {
                "trader": "demo:poster",
                "demo_wallet": True,
                "side": "buy",
                "outcome_id": yes,
                "price_bps": 5000,
                "quantity": 1,
                "post_only": True,
            },
        )


def test_professional_upgrade_manifest_is_valid():
    report = validate_upgrade_manifest(Path(__file__).resolve().parents[1])
    assert report["ok"] is True
    assert report["workstream_count"] >= 15
    assert report["production_claim"] is False


def test_imported_polymarket_market_auto_resolution_queue(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Did the imported source resolve YES?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "sandbox_short_mode": True,
            "external_source": "polymarket_gamma",
            "external_id": "pm-test",
            "source_end_time": 1,
            "source_winning_outcome_label": "YES",
            "auto_resolution": True,
        }
    )
    assert market["auto_resolution"]["status"] == "resolved"
    assert market["status"] == "resolved"
    assert market["winning_outcome_id"] == market["outcomes"][0]["outcome_id"]


def test_imported_polymarket_market_waits_for_source_winner(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Did the imported source finish without a winner?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "sandbox_short_mode": True,
            "external_source": "polymarket_gamma",
            "external_id": "pm-pending",
            "source_end_time": 1,
            "auto_resolution": True,
        }
    )
    assert market["status"] == "open"
    assert market["auto_resolution"]["status"] == "awaiting_source_result"


def test_auto_resolution_pays_out_open_positions_like_a_manual_resolve(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Will the imported market pay out its winning side automatically?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "sandbox_short_mode": True,
            "external_source": "polymarket_gamma",
            "external_id": "pm-payout",
        }
    )
    mid = market["market_id"]
    yes = market["outcomes"][0]["outcome_id"]
    store.place_market_order(
        mid,
        {
            "trader": "demo:maker",
            "demo_wallet": True,
            "side": "sell",
            "outcome_id": yes,
            "price_bps": 5000,
            "quantity": 4,
        },
    )
    store.place_market_order(
        mid,
        {
            "trader": "demo:winner",
            "demo_wallet": True,
            "side": "buy",
            "outcome_id": yes,
            "order_type": "market",
            "quantity": 4,
        },
    )
    positions_before = store.market_positions(mid, "demo:winner")
    balance_before = int(positions_before["portfolios"][0]["wallet"]["balance_sats"])

    data = store.load()
    m = data["prediction_markets"][mid]
    m["auto_resolution"] = {
        "enabled": True,
        "source": "polymarket_gamma",
        "source_end_time": 1,
        "source_winning_outcome_label": "YES",
        "status": "queued",
    }
    m["close_time"] = 1
    store.save(data)

    resynced = store.prediction_market(mid)
    assert resynced["status"] == "resolved"
    assert resynced["auto_resolution"]["status"] == "resolved"
    assert resynced["resolution_workflow"]["status"] == "auto_resolved_from_source"
    assert resynced["resolution_workflow"]["operator_approved"] is False

    positions_after = store.market_positions(mid, "demo:winner")
    balance_after = int(positions_after["portfolios"][0]["wallet"]["balance_sats"])
    assert balance_after > balance_before, "auto-resolution must pay out winning positions, not just flip status"
    assert not any(order["status"] == "open" for order in resynced["orders"])


def test_sync_market_auto_resolution_completes_when_the_live_source_has_a_winner(tmp_path: Path, monkeypatch):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Will the live poller pick up a real winner?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "external_source": "polymarket_gamma",
            "external_id": "pm-live",
            "condition_id": "cond-live",
            "source_end_time": 1,
            "auto_resolution": True,
        }
    )
    mid = market["market_id"]
    assert market["auto_resolution"]["status"] == "awaiting_source_result"

    _patch_gamma_api(monkeypatch, [{"resolved": True, "winningOutcome": "YES"}])
    synced = store.sync_market_auto_resolution(mid)

    assert synced["status"] == "resolved"
    assert synced["auto_resolution"]["status"] == "resolved"
    assert synced["auto_resolution"]["last_source_check_ok"] is True
    assert synced["winning_outcome_id"] == market["outcomes"][0]["outcome_id"]


def test_sync_market_auto_resolution_leaves_market_open_when_source_not_yet_resolved(tmp_path: Path, monkeypatch):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {
            "question": "Will the live poller wait if Polymarket hasn't resolved yet?",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "external_source": "polymarket_gamma",
            "external_id": "pm-pending-live",
            "source_end_time": 1,
            "auto_resolution": True,
        }
    )
    mid = market["market_id"]

    _patch_gamma_api(monkeypatch, [{"resolved": False}])
    synced = store.sync_market_auto_resolution(mid)

    assert synced["status"] == "open"
    assert synced["auto_resolution"]["status"] == "awaiting_source_result"
    assert synced["auto_resolution"]["last_source_check_ok"] is True


def test_sync_market_auto_resolution_rejects_non_polymarket_sources(tmp_path: Path):
    store = AppStore(tmp_path)
    market = store.create_prediction_market(
        {"question": "Manual market", "outcomes": ["YES", "NO"], "legal_acknowledged": True}
    )
    with pytest.raises(AppError, match="no auto-resolution source configured"):
        store.sync_market_auto_resolution(market["market_id"])


def test_sync_all_pending_auto_resolutions_only_touches_awaiting_markets(tmp_path: Path, monkeypatch):
    store = AppStore(tmp_path)
    pending = store.create_prediction_market(
        {
            "question": "Pending market",
            "outcomes": ["YES", "NO"],
            "legal_acknowledged": True,
            "external_source": "polymarket_gamma",
            "external_id": "pm-bulk-1",
            "source_end_time": 1,
            "auto_resolution": True,
        }
    )
    store.create_prediction_market({"question": "Untouched manual market", "outcomes": ["YES", "NO"]})

    _patch_gamma_api(monkeypatch, [{"resolved": True, "winningOutcome": "YES"}])
    report = store.sync_all_pending_auto_resolutions()

    assert report["checked"] == 1
    assert report["results"][0]["market_id"] == pending["market_id"]
    assert report["results"][0]["status"] == "resolved"
