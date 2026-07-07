"""Prediction-market demo engine for the NetCoin app layer.

This module is intentionally app-layer/testnet-only.  It gives the Labs UI a
richer order model, demo-wallet accounting, cancellation, analytics, resolution
workflow, and a read-only Polymarket bridge without changing consensus rules.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..crypto import validate_address
from ..tx import amount_to_sats, sats_to_amount
from . import AppError, clean_id, now, parse_amount_sats
from .security import PREDICTION_MARKET_WARNING, RESTRICTED_MARKET_TERMS, market_compliance_record

DEFAULT_DEMO_BALANCE_SATS = amount_to_sats("10000")
DEFAULT_UNIT_PAYOUT_SATS = amount_to_sats("1")
MAX_POLYMARKET_LIMIT = 25


def _deepcopy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _bps_to_sats(price_bps: int, unit_payout_sats: int) -> int:
    return unit_payout_sats * int(price_bps) // 10_000


def _share_cost_sats(price_bps: int, quantity: int, unit_payout_sats: int) -> int:
    return _bps_to_sats(price_bps, unit_payout_sats) * int(quantity)


def _short_collateral_sats(price_bps: int, quantity: int, unit_payout_sats: int) -> int:
    return max(0, unit_payout_sats - _bps_to_sats(price_bps, unit_payout_sats)) * int(quantity)


def _price_decimal(price_bps: int) -> str:
    return f"{int(price_bps) / 10_000:.4f}".rstrip("0").rstrip(".")


def _market_event(market: dict[str, Any], event: str, payload: dict[str, Any]) -> None:
    rec = {"event_id": clean_id("mev"), "event": event, "payload": payload, "created_at": now()}
    market.setdefault("audit_trail", []).append(rec)
    market["audit_trail"] = market.get("audit_trail", [])[-500:]


def _normalize_trader_id(payload: dict[str, Any]) -> str:
    raw = str(payload.get("trader_address") or payload.get("address") or payload.get("trader") or "").strip()
    if validate_address(raw):
        return raw
    allow_demo = bool(payload.get("allow_unverified_demo") or payload.get("demo_wallet") or str(raw).startswith("demo:"))
    if not allow_demo:
        raise AppError("trader_address must be a valid NetCoin address, or pass allow_unverified_demo=true for Labs play-money traders")
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw.replace("demo:", "", 1)).strip("-")[:40]
    if not cleaned:
        cleaned = "trader"
    return f"demo:{cleaned}"


def _ensure_market_wallet(market: dict[str, Any], trader: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    wallets = market.setdefault("wallets", {})
    if trader not in wallets:
        initial = int(payload.get("initial_balance_sats") or payload.get("demo_balance_sats") or DEFAULT_DEMO_BALANCE_SATS)
        wallets[trader] = {
            "trader_id": trader,
            "balance_sats": initial,
            "reserved_sats": 0,
            "realized_pnl_sats": 0,
            "total_deposited_sats": initial,
            "created_at": now(),
            "updated_at": now(),
        }
    wallet = wallets[trader]
    wallet.setdefault("balance_sats", DEFAULT_DEMO_BALANCE_SATS)
    wallet.setdefault("reserved_sats", 0)
    wallet.setdefault("realized_pnl_sats", 0)
    wallet["available_sats"] = max(0, int(wallet.get("balance_sats", 0)) - int(wallet.get("reserved_sats", 0)))
    wallet["balance"] = sats_to_amount(int(wallet.get("balance_sats", 0)))
    wallet["reserved"] = sats_to_amount(int(wallet.get("reserved_sats", 0)))
    wallet["available"] = sats_to_amount(wallet["available_sats"])
    wallet["updated_at"] = now()
    return wallet


def _reserve(wallet: dict[str, Any], amount_sats: int) -> None:
    amount_sats = int(amount_sats)
    if amount_sats <= 0:
        return
    available = int(wallet.get("balance_sats", 0)) - int(wallet.get("reserved_sats", 0))
    if available < amount_sats:
        raise AppError("insufficient play-money balance for required collateral/reserve")
    wallet["reserved_sats"] = int(wallet.get("reserved_sats", 0)) + amount_sats
    wallet["available_sats"] = available - amount_sats
    wallet["reserved"] = sats_to_amount(wallet["reserved_sats"])
    wallet["available"] = sats_to_amount(wallet["available_sats"])


def _release(wallet: dict[str, Any], amount_sats: int) -> None:
    amount_sats = int(amount_sats)
    if amount_sats <= 0:
        return
    wallet["reserved_sats"] = max(0, int(wallet.get("reserved_sats", 0)) - amount_sats)
    wallet["available_sats"] = max(0, int(wallet.get("balance_sats", 0)) - int(wallet.get("reserved_sats", 0)))
    wallet["reserved"] = sats_to_amount(wallet["reserved_sats"])
    wallet["available"] = sats_to_amount(wallet["available_sats"])


def _format_wallets(market: dict[str, Any]) -> None:
    for trader in list(market.get("wallets", {})):
        _ensure_market_wallet(market, trader)


def _order_reserved_for_remaining(order: dict[str, Any], remaining: int) -> int:
    original = max(1, int(order.get("quantity", 1) or 1))
    total = int(order.get("reserved_sats_initial", 0) or 0)
    return total * int(remaining) // original


def _release_filled_reserve(market: dict[str, Any], order: dict[str, Any], previous_remaining: int, new_remaining: int) -> None:
    prev_reserved = _order_reserved_for_remaining(order, previous_remaining)
    next_reserved = _order_reserved_for_remaining(order, new_remaining)
    release = max(0, prev_reserved - next_reserved)
    order["reserved_sats_remaining"] = next_reserved
    wallet = _ensure_market_wallet(market, order["trader_address"])
    _release(wallet, release)


def _available_position(market: dict[str, Any], trader: str, outcome_id: str) -> int:
    positions = market.setdefault("positions", {})
    return int(positions.get(trader, {}).get(outcome_id, 0) or 0)


def _add_position(market: dict[str, Any], trader: str, outcome_id: str, delta: int) -> None:
    positions = market.setdefault("positions", {})
    positions.setdefault(trader, {}).setdefault(outcome_id, 0)
    positions[trader][outcome_id] = int(positions[trader].get(outcome_id, 0) or 0) + int(delta)


def _public_order(order: dict[str, Any]) -> dict[str, Any]:
    result = _deepcopy(order)
    result["price"] = _price_decimal(int(result.get("price_bps", 0)))
    if "reserved_sats_initial" in result:
        result["reserved_initial"] = sats_to_amount(int(result.get("reserved_sats_initial", 0)))
        result["reserved_remaining"] = sats_to_amount(int(result.get("reserved_sats_remaining", 0)))
    return result


def _order_sort_key(side: str):
    if side == "buy":
        return lambda order: (-int(order.get("price_bps", 0)), int(order.get("created_at", 0)), str(order.get("order_id", "")))
    return lambda order: (int(order.get("price_bps", 0)), int(order.get("created_at", 0)), str(order.get("order_id", "")))


def _build_orderbook(market: dict[str, Any]) -> dict[str, Any]:
    outcome_ids = [o["outcome_id"] for o in market.get("outcomes", [])]
    orderbook: dict[str, Any] = {oid: {"buys": [], "sells": [], "best_bid_bps": None, "best_ask_bps": None, "spread_bps": None} for oid in outcome_ids}
    for order in market.get("orders", []):
        if order.get("status") != "open" or int(order.get("remaining", 0) or 0) <= 0:
            continue
        oid = order.get("outcome_id")
        if oid not in orderbook:
            continue
        side_key = "buys" if order.get("side") == "buy" else "sells"
        orderbook[oid][side_key].append(_public_order(order))
    for oid, book in orderbook.items():
        book["buys"].sort(key=_order_sort_key("buy"))
        book["sells"].sort(key=_order_sort_key("sell"))
        bid = int(book["buys"][0]["price_bps"]) if book["buys"] else None
        ask = int(book["sells"][0]["price_bps"]) if book["sells"] else None
        book["best_bid_bps"] = bid
        book["best_ask_bps"] = ask
        book["best_bid"] = _price_decimal(bid) if bid is not None else None
        book["best_ask"] = _price_decimal(ask) if ask is not None else None
        book["spread_bps"] = (ask - bid) if bid is not None and ask is not None else None
        book["spread"] = _price_decimal(book["spread_bps"]) if book["spread_bps"] is not None else None
    return orderbook


def _market_stats(market: dict[str, Any], orderbook: dict[str, Any]) -> dict[str, Any]:
    trades = market.get("trades", [])
    unit = int(market.get("unit_payout_sats", DEFAULT_UNIT_PAYOUT_SATS) or DEFAULT_UNIT_PAYOUT_SATS)
    volume_shares = sum(int(t.get("quantity", 0) or 0) for t in trades)
    volume_sats = sum(_share_cost_sats(int(t.get("price_bps", 0) or 0), int(t.get("quantity", 0) or 0), unit) for t in trades)
    open_interest = 0
    for positions in market.get("positions", {}).values():
        open_interest += sum(max(0, int(q or 0)) for q in positions.values())
    liquidity_shares = sum(int(o.get("remaining", 0) or 0) for o in market.get("orders", []) if o.get("status") == "open")
    last_trade = trades[-1] if trades else None
    implied: dict[str, Any] = {}
    for outcome in market.get("outcomes", []):
        oid = outcome["outcome_id"]
        book = orderbook.get(oid, {})
        bid = book.get("best_bid_bps")
        ask = book.get("best_ask_bps")
        last = None
        for trade in reversed(trades):
            if trade.get("outcome_id") == oid:
                last = int(trade.get("price_bps", 0) or 0)
                break
        ref = ((bid + ask) // 2 if bid is not None and ask is not None else last if last is not None else bid if bid is not None else ask)
        implied[oid] = {
            "label": outcome.get("label"),
            "probability_bps": ref,
            "probability": _price_decimal(ref) if ref is not None else None,
            "last_price_bps": last,
            "last_price": _price_decimal(last) if last is not None else None,
        }
    return {
        "volume_shares": volume_shares,
        "volume_sats": volume_sats,
        "volume": sats_to_amount(volume_sats),
        "liquidity_shares": liquidity_shares,
        "open_interest_shares": open_interest,
        "trade_count": len(trades),
        "last_trade": _deepcopy(last_trade),
        "implied_probabilities": implied,
        "top_traders": _top_traders(market),
    }


def _top_traders(market: dict[str, Any]) -> list[dict[str, Any]]:
    scores: dict[str, int] = {}
    for trade in market.get("trades", []):
        qty = int(trade.get("quantity", 0) or 0)
        scores[trade.get("buyer", "")] = scores.get(trade.get("buyer", ""), 0) + qty
        scores[trade.get("seller", "")] = scores.get(trade.get("seller", ""), 0) + qty
    return [{"trader_id": trader, "shares_traded": shares} for trader, shares in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10] if trader]


def _analytics_series(market: dict[str, Any]) -> dict[str, Any]:
    points = []
    cumulative_volume = 0
    for trade in market.get("trades", []):
        cumulative_volume += int(trade.get("quantity", 0) or 0)
        points.append({
            "created_at": trade.get("created_at"),
            "outcome_id": trade.get("outcome_id"),
            "price_bps": trade.get("price_bps"),
            "price": _price_decimal(int(trade.get("price_bps", 0) or 0)),
            "quantity": trade.get("quantity"),
            "cumulative_volume_shares": cumulative_volume,
        })
    return {"price_points": points[-250:], "volume_points": points[-250:]}


def _surveillance_report(market: dict[str, Any]) -> dict[str, Any]:
    """Generate market-integrity alerts for Labs/demo markets.

    This is surveillance, not enforcement by itself. Operators can use the
    alerts to pause creation, reject resolution, or investigate abuse patterns.
    """
    alerts: list[dict[str, Any]] = []
    trades = list(market.get("trades", []))
    orders = list(market.get("orders", []))
    wallets = market.get("wallets", {})

    for trade in trades:
        if trade.get("buyer") == trade.get("seller") or trade.get("maker") == trade.get("taker"):
            alerts.append({"code": "wash_trade", "severity": "critical", "detail": "same trader appears on both sides of a trade", "trade_id": trade.get("trade_id")})

    volume_by_trader: dict[str, int] = {}
    for trade in trades:
        qty = int(trade.get("quantity", 0) or 0)
        volume_by_trader[trade.get("buyer", "")] = volume_by_trader.get(trade.get("buyer", ""), 0) + qty
        volume_by_trader[trade.get("seller", "")] = volume_by_trader.get(trade.get("seller", ""), 0) + qty
    total_sides = sum(volume_by_trader.values())
    if total_sides:
        leader, leader_qty = max(volume_by_trader.items(), key=lambda kv: kv[1])
        share_bps = int(leader_qty * 10_000 / total_sides)
        if share_bps >= int(market.get("surveillance_thresholds", {}).get("concentration_bps", 8000)):
            alerts.append({"code": "volume_concentration", "severity": "medium", "detail": "one trader dominates traded volume", "trader": leader, "share_bps": share_bps})

    by_outcome: dict[str, list[int]] = {}
    for trade in trades:
        by_outcome.setdefault(str(trade.get("outcome_id")), []).append(int(trade.get("price_bps", 0) or 0))
    for outcome_id, prices in by_outcome.items():
        if len(prices) >= 2 and abs(prices[-1] - prices[0]) >= int(market.get("surveillance_thresholds", {}).get("rapid_move_bps", 4000)):
            alerts.append({"code": "rapid_price_move", "severity": "medium", "detail": "large price move across observed trades", "outcome_id": outcome_id, "first_bps": prices[0], "last_bps": prices[-1]})

    open_orders = [o for o in orders if o.get("status") == "open"]
    if market.get("status") in {"closed", "resolved"} and open_orders:
        alerts.append({"code": "open_orders_after_close", "severity": "high", "detail": "market has open orders after close/resolution", "count": len(open_orders)})
    if not wallets and (orders or trades):
        alerts.append({"code": "missing_wallet_ledger", "severity": "high", "detail": "orders/trades exist but market wallet ledger is empty"})
    if any(int(w.get("balance_sats", 0) or 0) < 0 for w in wallets.values()):
        alerts.append({"code": "negative_demo_wallet", "severity": "high", "detail": "demo wallet balance went negative"})

    workflow = market.get("resolution_workflow", {})
    disputes = workflow.get("disputes", []) or []
    if workflow.get("status") == "pending_operator_approval" and now() - int((workflow.get("pending_resolution") or {}).get("requested_at", now()) or now()) > int(market.get("dispute_window_seconds", 86400)):
        alerts.append({"code": "resolution_pending_over_dispute_window", "severity": "medium", "detail": "pending resolution is older than the configured dispute window"})
    if disputes:
        alerts.append({"code": "active_resolution_disputes", "severity": "medium", "detail": "market has resolution dispute records", "count": len(disputes)})

    return {
        "ok": not any(a["severity"] in {"high", "critical"} for a in alerts),
        "alert_count": len(alerts),
        "alerts": alerts,
        "thresholds": market.get("surveillance_thresholds", {"concentration_bps": 8000, "rapid_move_bps": 4000}),
        "last_checked_at": now(),
    }


def _hydrate_market(market: dict[str, Any]) -> dict[str, Any]:
    _format_wallets(market)
    orderbook = _build_orderbook(market)
    result = _deepcopy(market)
    result["orders"] = [_public_order(o) for o in market.get("orders", [])]
    result["open_orders"] = [_public_order(o) for o in market.get("orders", []) if o.get("status") == "open"]
    result["orderbook"] = orderbook
    result["stats"] = _market_stats(market, orderbook)
    result["analytics"] = _analytics_series(market)
    result["surveillance"] = _surveillance_report(market)
    result["unit_payout"] = sats_to_amount(int(market.get("unit_payout_sats", DEFAULT_UNIT_PAYOUT_SATS) or DEFAULT_UNIT_PAYOUT_SATS))
    result["collateral_pool"] = sats_to_amount(int(market.get("collateral_pool_sats", 0) or 0))
    result["warning"] = market.get("warning") or PREDICTION_MARKET_WARNING
    result.setdefault("compliance", market_compliance_record(
        mode=str(market.get("mode", "testnet_demo")),
        legal_acknowledged=bool(market.get("legal_acknowledged", False)),
        operator_override=bool(market.get("operator_override", False)),
    ))
    return result


def create_prediction_market_impl(store: Any, payload: dict[str, Any]) -> dict[str, Any]:
    question = str(payload.get("question") or "").strip()
    if not question:
        raise AppError("market question is required")
    outcomes = [str(x).strip().upper() for x in (payload.get("outcomes") or ["YES", "NO"]) if str(x).strip()]
    if len(outcomes) < 2:
        raise AppError("market requires at least two outcomes")
    market_id = str(payload.get("market_id") or clean_id("mkt"))
    mode = str(payload.get("mode") or "testnet_demo")
    if mode not in {"testnet_demo", "play_money", "private_dev"}:
        raise AppError("prediction markets are restricted to testnet_demo, play_money, or private_dev modes")
    if store.load().get("security_settings", {}).get("prediction_markets_require_ack") and not bool(payload.get("legal_acknowledged", False)):
        raise AppError("prediction market creation requires legal_acknowledged=true in this deployment")
    # Preserve the existing environment gate.
    import os
    if os.environ.get("NETCOIN_REQUIRE_MARKET_LEGAL_ACK", "0") == "1" and not bool(payload.get("legal_acknowledged", False)):
        raise AppError("prediction market creation requires legal_acknowledged=true in this deployment")
    lowered_question = question.lower()
    if any(term in lowered_question for term in RESTRICTED_MARKET_TERMS) and not bool(payload.get("operator_override", False)):
        raise AppError("restricted prediction-market topic requires operator_override=true and legal review")
    unit_payout_sats = parse_amount_sats(payload.get("unit_payout_sats", payload.get("unit_payout", "1")), "unit payout")
    if unit_payout_sats <= 0:
        raise AppError("unit payout must be positive")
    sandbox_short_mode = bool(payload.get("sandbox_short_mode", True))
    record = {
        "market_id": market_id,
        "question": question[:240],
        "description": str(payload.get("description") or "")[:2000],
        "outcomes": [{"outcome_id": f"out{i+1}", "label": label} for i, label in enumerate(outcomes)],
        "oracle": str(payload.get("oracle") or "manual")[:120],
        "resolution_source": str(payload.get("resolution_source") or "")[:500],
        "mode": mode,
        "status": "open",
        "close_time": int(payload.get("close_time", now() + 604800) or now() + 604800),
        "orders": [],
        "trades": [],
        "positions": {},
        "wallets": {},
        "short_collateral": {},
        "collateral_pool_sats": 0,
        "unit_payout_sats": unit_payout_sats,
        "created_at": now(),
        "updated_at": now(),
        "warning": PREDICTION_MARKET_WARNING,
        "legal_acknowledged": bool(payload.get("legal_acknowledged", False)),
        "operator_override": bool(payload.get("operator_override", False)),
        "compliance_status": "demo_restricted",
        "compliance": market_compliance_record(mode=mode, legal_acknowledged=bool(payload.get("legal_acknowledged", False)), operator_override=bool(payload.get("operator_override", False))),
        "sandbox_short_mode": sandbox_short_mode,
        "resolution_workflow": {
            "status": "unresolved",
            "evidence_url": "",
            "operator_approved": False,
            "pending_resolution": None,
            "disputes": [],
        },
        "dispute_window_seconds": int(payload.get("dispute_window_seconds", 86400) or 86400),
        "surveillance_thresholds": {
            "concentration_bps": int(payload.get("concentration_bps", 8000) or 8000),
            "rapid_move_bps": int(payload.get("rapid_move_bps", 4000) or 4000),
        },
        "audit_trail": [],
        "external_source": payload.get("external_source") or None,
    }
    data = store.load()
    data.setdefault("prediction_markets", {})[market_id] = record
    data.setdefault("contracts", {})[market_id] = {"contract_id": market_id, "contract_type": "prediction_market", "status": record["status"], "terms": record, "created_at": now(), "updated_at": now()}
    _market_event(record, "market.created", {"market_id": market_id})
    store._record_contract_event(data, "market.created", {"market_id": market_id})
    store.save(data)
    return prediction_market_impl(store, market_id)


def prediction_market_impl(store: Any, market_id: str) -> dict[str, Any]:
    m = store.load().get("prediction_markets", {}).get(market_id)
    if not m:
        raise AppError("prediction market not found")
    return _hydrate_market(m)


def list_prediction_markets_impl(store: Any) -> dict[str, Any]:
    data = store.load()
    markets = [_hydrate_market(x) for x in data.get("prediction_markets", {}).values()]
    markets.sort(key=lambda m: (m.get("status") != "open", -int(m.get("created_at", 0) or 0)))
    totals = {
        "count": len(markets),
        "open": sum(1 for m in markets if m.get("status") == "open"),
        "closed": sum(1 for m in markets if m.get("status") == "closed"),
        "resolved": sum(1 for m in markets if m.get("status") == "resolved"),
        "volume_sats": sum(int(m.get("stats", {}).get("volume_sats", 0) or 0) for m in markets),
    }
    totals["volume"] = sats_to_amount(totals["volume_sats"])
    return {"markets": markets, "totals": totals, "warning": PREDICTION_MARKET_WARNING}


def _find_order(market: dict[str, Any], order_id: str) -> dict[str, Any] | None:
    for order in market.get("orders", []):
        if order.get("order_id") == order_id:
            return order
    return None


def _match_order(market: dict[str, Any], order: dict[str, Any]) -> None:
    opposite = "sell" if order["side"] == "buy" else "buy"
    candidates = [
        other for other in market.get("orders", [])
        if other.get("status") == "open"
        and other.get("outcome_id") == order.get("outcome_id")
        and other.get("side") == opposite
        and other.get("trader_address") != order.get("trader_address")
    ]
    candidates.sort(key=_order_sort_key(opposite))
    unit = int(market.get("unit_payout_sats", DEFAULT_UNIT_PAYOUT_SATS) or DEFAULT_UNIT_PAYOUT_SATS)
    for other in candidates:
        if int(order.get("remaining", 0) or 0) <= 0:
            break
        other_price = int(other.get("price_bps", 0) or 0)
        order_price = int(order.get("price_bps", 0) or 0)
        crosses = order_price >= other_price if order["side"] == "buy" else other_price >= order_price
        if not crosses:
            continue
        prev_order_remaining = int(order.get("remaining", 0) or 0)
        prev_other_remaining = int(other.get("remaining", 0) or 0)
        qty = min(prev_order_remaining, prev_other_remaining)
        if qty <= 0:
            continue
        trade_price = other_price  # maker price
        buyer = order["trader_address"] if order["side"] == "buy" else other["trader_address"]
        seller = other["trader_address"] if order["side"] == "buy" else order["trader_address"]
        maker = other["trader_address"]
        taker = order["trader_address"]
        buyer_wallet = _ensure_market_wallet(market, buyer)
        seller_wallet = _ensure_market_wallet(market, seller)
        trade_cost = _share_cost_sats(trade_price, qty, unit)
        # Filled/open reserve is no longer needed for the matched portion.
        _release_filled_reserve(market, order, prev_order_remaining, prev_order_remaining - qty)
        _release_filled_reserve(market, other, prev_other_remaining, prev_other_remaining - qty)
        # Demo wallet cash ledger.  The buyer pays the trade price; the seller receives it.
        buyer_wallet["balance_sats"] = int(buyer_wallet.get("balance_sats", 0)) - trade_cost
        seller_wallet["balance_sats"] = int(seller_wallet.get("balance_sats", 0)) + trade_cost
        available_before_sell = _available_position(market, seller, order["outcome_id"])
        short_qty = max(0, qty - max(0, available_before_sell))
        if short_qty:
            collateral = _short_collateral_sats(trade_price, short_qty, unit)
            seller_wallet["balance_sats"] = int(seller_wallet.get("balance_sats", 0)) - collateral
            market["collateral_pool_sats"] = int(market.get("collateral_pool_sats", 0) or 0) + collateral
            sc = market.setdefault("short_collateral", {}).setdefault(seller, {}).setdefault(order["outcome_id"], 0)
            market["short_collateral"][seller][order["outcome_id"]] = int(sc) + collateral
        _add_position(market, buyer, order["outcome_id"], qty)
        _add_position(market, seller, order["outcome_id"], -qty)
        order["remaining"] = prev_order_remaining - qty
        other["remaining"] = prev_other_remaining - qty
        if order["remaining"] <= 0:
            order["status"] = "filled"
            order["filled_at"] = now()
        if other["remaining"] <= 0:
            other["status"] = "filled"
            other["filled_at"] = now()
        trade = {
            "trade_id": clean_id("trd"),
            "market_id": market["market_id"],
            "outcome_id": order["outcome_id"],
            "quantity": qty,
            "price_bps": trade_price,
            "price": _price_decimal(trade_price),
            "buyer": buyer,
            "seller": seller,
            "maker": maker,
            "taker": taker,
            "maker_order_id": other["order_id"],
            "taker_order_id": order["order_id"],
            "maker_side": other["side"],
            "taker_side": order["side"],
            "created_at": now(),
            "cost_sats": trade_cost,
            "cost": sats_to_amount(trade_cost),
        }
        market.setdefault("trades", []).append(trade)
        order.setdefault("fills", []).append(trade["trade_id"])
        other.setdefault("fills", []).append(trade["trade_id"])
        _market_event(market, "market.trade", {"market_id": market["market_id"], "trade_id": trade["trade_id"], "quantity": qty, "price_bps": trade_price})
        _ensure_market_wallet(market, buyer)
        _ensure_market_wallet(market, seller)


def place_market_order_impl(store: Any, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = store.load()
    m = data.get("prediction_markets", {}).get(market_id)
    if not m:
        raise AppError("prediction market not found")
    if m.get("status") != "open" or now() > int(m.get("close_time", 0) or 0):
        m["status"] = "closed"
        m["updated_at"] = now()
        store.save(data)
        raise AppError("prediction market is closed")
    outcome_id = str(payload.get("outcome_id") or "").strip()
    if outcome_id not in {o["outcome_id"] for o in m.get("outcomes", [])}:
        raise AppError("invalid market outcome")
    side = str(payload.get("side") or "buy").lower()
    if side not in {"buy", "sell"}:
        raise AppError("side must be buy or sell")
    trader = _normalize_trader_id(payload)
    wallet = _ensure_market_wallet(m, trader, payload)
    quantity = int(payload.get("quantity", payload.get("shares", 0)) or 0)
    raw_price = payload.get("price_bps")
    price_bps = int(raw_price if raw_price is not None and str(raw_price) != "" else round(float(payload.get("price", 0)) * 10000))
    if quantity <= 0:
        raise AppError("quantity must be positive")
    if not 1 <= price_bps <= 9999:
        raise AppError("price_bps must be 1..9999")
    unit = int(m.get("unit_payout_sats", DEFAULT_UNIT_PAYOUT_SATS) or DEFAULT_UNIT_PAYOUT_SATS)
    current_pos = _available_position(m, trader, outcome_id)
    short_needed = side == "sell" and current_pos < quantity
    if short_needed and not bool(m.get("sandbox_short_mode", False) or payload.get("sandbox_short_mode", False)):
        raise AppError("cannot sell more shares than the trader holds unless sandbox_short_mode is enabled")
    reserve_sats = _share_cost_sats(price_bps, quantity, unit) if side == "buy" else (_short_collateral_sats(price_bps, max(0, quantity - max(0, current_pos)), unit) if short_needed else 0)
    _reserve(wallet, reserve_sats)
    order = {
        "order_id": clean_id("ord"),
        "market_id": market_id,
        "outcome_id": outcome_id,
        "side": side,
        "trader_address": trader,
        "quantity": quantity,
        "remaining": quantity,
        "price_bps": price_bps,
        "price": _price_decimal(price_bps),
        "status": "open",
        "role": "taker",
        "type": str(payload.get("type") or "limit"),
        "maker": None,
        "taker": trader,
        "fills": [],
        "reserved_sats_initial": reserve_sats,
        "reserved_sats_remaining": reserve_sats,
        "collateralized_short": bool(short_needed),
        "created_at": now(),
        "updated_at": now(),
    }
    _match_order(m, order)
    if int(order.get("remaining", 0) or 0) > 0:
        order["role"] = "maker"
        order["maker"] = trader
        order["status"] = "open"
    else:
        order["status"] = "filled"
        order["filled_at"] = now()
    m.setdefault("orders", []).append(order)
    m["updated_at"] = now()
    store._record_contract_event(data, "market.order", {"market_id": market_id, "order_id": order["order_id"], "status": order["status"]})
    _market_event(m, "market.order", {"market_id": market_id, "order_id": order["order_id"], "status": order["status"]})
    store.save(data)
    return prediction_market_impl(store, market_id)


def cancel_market_order_impl(store: Any, market_id: str, order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    data = store.load()
    m = data.get("prediction_markets", {}).get(market_id)
    if not m:
        raise AppError("prediction market not found")
    order = _find_order(m, order_id)
    if not order:
        raise AppError("market order not found")
    if order.get("status") != "open":
        raise AppError("only open market orders can be canceled")
    actor = str(payload.get("trader_address") or payload.get("address") or payload.get("trader") or "").strip()
    if actor:
        actor_norm = _normalize_trader_id(payload)
        if actor_norm != order.get("trader_address") and not payload.get("operator_override"):
            raise AppError("only the order owner or an operator override can cancel this order")
    wallet = _ensure_market_wallet(m, order["trader_address"])
    _release(wallet, int(order.get("reserved_sats_remaining", 0) or 0))
    order["reserved_sats_remaining"] = 0
    order["status"] = "canceled"
    order["canceled_at"] = now()
    order["updated_at"] = now()
    m["updated_at"] = now()
    _market_event(m, "market.order_canceled", {"market_id": market_id, "order_id": order_id})
    store._record_contract_event(data, "market.order_canceled", {"market_id": market_id, "order_id": order_id})
    store.save(data)
    return prediction_market_impl(store, market_id)


def request_market_resolution_impl(store: Any, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = store.load()
    m = data.get("prediction_markets", {}).get(market_id)
    if not m:
        raise AppError("prediction market not found")
    winning = str(payload.get("winning_outcome_id") or payload.get("winner") or "").strip()
    if winning not in {o["outcome_id"] for o in m.get("outcomes", [])}:
        raise AppError("invalid winning outcome")
    m.setdefault("resolution_workflow", {})["status"] = "pending_operator_approval"
    m["resolution_workflow"]["pending_resolution"] = {
        "winning_outcome_id": winning,
        "resolution_note": str(payload.get("resolution_note") or "")[:1000],
        "evidence_url": str(payload.get("evidence_url") or payload.get("resolution_source") or "")[:500],
        "requested_at": now(),
    }
    m["status"] = "closed"
    m["updated_at"] = now()
    _market_event(m, "market.resolution_requested", {"market_id": market_id, "winning_outcome_id": winning})
    store.save(data)
    return prediction_market_impl(store, market_id)


def dispute_market_resolution_impl(store: Any, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = store.load()
    m = data.get("prediction_markets", {}).get(market_id)
    if not m:
        raise AppError("prediction market not found")
    actor = str(payload.get("actor") or payload.get("trader_address") or payload.get("trader") or "operator")[:120]
    dispute = {
        "dispute_id": clean_id("dsp"),
        "actor": actor,
        "reason": str(payload.get("reason") or "")[:1000],
        "evidence_url": str(payload.get("evidence_url") or "")[:500],
        "status": "open",
        "created_at": now(),
    }
    workflow = m.setdefault("resolution_workflow", {})
    workflow.setdefault("disputes", []).append(dispute)
    workflow["status"] = "disputed"
    m["status"] = "closed"
    m["updated_at"] = now()
    _market_event(m, "market.resolution_disputed", {"market_id": market_id, "dispute_id": dispute["dispute_id"]})
    store._record_contract_event(data, "market.resolution_disputed", {"market_id": market_id, "dispute_id": dispute["dispute_id"]})
    store.save(data)
    return prediction_market_impl(store, market_id)


def market_surveillance_impl(store: Any, market_id: str | None = None) -> dict[str, Any]:
    data = store.load()
    markets = data.get("prediction_markets", {})
    if market_id:
        m = markets.get(market_id)
        if not m:
            raise AppError("prediction market not found")
        return {"market_id": market_id, "surveillance": _surveillance_report(m)}
    reports = []
    for mid, market in markets.items():
        reports.append({"market_id": mid, "question": market.get("question"), "status": market.get("status"), "surveillance": _surveillance_report(market)})
    alerts = sum(int(r["surveillance"].get("alert_count", 0) or 0) for r in reports)
    high = [r for r in reports if not r["surveillance"].get("ok")]
    return {"markets": reports, "alert_count": alerts, "markets_with_high_alerts": len(high), "ok": len(high) == 0}


def resolve_prediction_market_impl(store: Any, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = store.load()
    m = data.get("prediction_markets", {}).get(market_id)
    if not m:
        raise AppError("prediction market not found")
    winning = str(payload.get("winning_outcome_id") or payload.get("winner") or "").strip()
    pending = m.get("resolution_workflow", {}).get("pending_resolution") or {}
    if not winning and pending:
        winning = str(pending.get("winning_outcome_id") or "")
    if winning not in {o["outcome_id"] for o in m.get("outcomes", [])}:
        raise AppError("invalid winning outcome")
    payout_per_share_sats = parse_amount_sats(payload.get("payout_per_share_sats", payload.get("payout_per_share", sats_to_amount(int(m.get("unit_payout_sats", DEFAULT_UNIT_PAYOUT_SATS) or DEFAULT_UNIT_PAYOUT_SATS)))), "payout per share")
    outputs = []
    demo_payouts = []
    for address, positions in m.get("positions", {}).items():
        qty = int(positions.get(winning, 0) or 0)
        if qty > 0:
            payout_sats = qty * payout_per_share_sats
            if validate_address(address):
                outputs.append({"address": address, "amount_sats": payout_sats})
            else:
                wallet = _ensure_market_wallet(m, address)
                wallet["balance_sats"] = int(wallet.get("balance_sats", 0)) + payout_sats
                wallet["realized_pnl_sats"] = int(wallet.get("realized_pnl_sats", 0)) + payout_sats
                demo_payouts.append({"trader_id": address, "amount_sats": payout_sats, "amount": sats_to_amount(payout_sats), "quantity": qty})
    # Release short collateral for losing outcomes back to demo wallets; winning shorts lose collateral.
    for trader, by_outcome in m.get("short_collateral", {}).items():
        for outcome_id, collateral_sats in by_outcome.items():
            collateral_sats = int(collateral_sats or 0)
            if outcome_id != winning and collateral_sats:
                wallet = _ensure_market_wallet(m, trader)
                wallet["balance_sats"] = int(wallet.get("balance_sats", 0)) + collateral_sats
                m["collateral_pool_sats"] = max(0, int(m.get("collateral_pool_sats", 0) or 0) - collateral_sats)
    payout_plan = store.plan_payout("prediction_market", outputs, memo=f"Resolve market {market_id}: {winning}") if outputs else {"outputs": [], "total_sats": 0, "total": "0", "status": "no_valid_chain_address_winners" if demo_payouts else "no_winning_positions", "kind": "prediction_market"}
    m["status"] = "resolved"
    m["winning_outcome_id"] = winning
    m["resolved_at"] = now()
    m["resolution_note"] = str(payload.get("resolution_note") or pending.get("resolution_note") or "")[:1000]
    m["resolution_source"] = str(payload.get("resolution_source") or payload.get("evidence_url") or pending.get("evidence_url") or m.get("resolution_source") or "")[:500]
    m["payout_plan"] = payout_plan
    m["demo_payouts"] = demo_payouts
    m["resolution_workflow"] = {
        "status": "operator_approved_resolved" if payload.get("operator_approved", True) else "resolved",
        "evidence_url": m.get("resolution_source", ""),
        "operator_approved": bool(payload.get("operator_approved", True)),
        "winning_outcome_id": winning,
        "resolved_at": m["resolved_at"],
    }
    for order in m.get("orders", []):
        if order.get("status") == "open":
            wallet = _ensure_market_wallet(m, order["trader_address"])
            _release(wallet, int(order.get("reserved_sats_remaining", 0) or 0))
            order["reserved_sats_remaining"] = 0
            order["status"] = "canceled"
            order["canceled_at"] = now()
            order["cancel_reason"] = "market_resolved"
    m["updated_at"] = now()
    _market_event(m, "market.resolved", {"market_id": market_id, "winning_outcome_id": winning})
    store._record_contract_event(data, "market.resolved", {"market_id": market_id, "winning_outcome_id": winning})
    store.save(data)
    return prediction_market_impl(store, market_id)


def polymarket_markets_impl(store: Any, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    query = query or {}
    limit_raw = (query.get("limit") or ["10"])[0]
    try:
        limit = max(1, min(MAX_POLYMARKET_LIMIT, int(limit_raw)))
    except ValueError:
        limit = 10
    active = (query.get("active") or ["true"])[0]
    params = urllib.parse.urlencode({"limit": limit, "active": active})
    url = f"https://gamma-api.polymarket.com/markets?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NetCoin-Labs/0.12"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read(1_000_000).decode("utf-8")
            payload = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"source": "polymarket_gamma", "mode": "read_only", "ok": False, "error": str(exc), "markets": []}
    markets = payload if isinstance(payload, list) else payload.get("markets", []) if isinstance(payload, dict) else []
    normalized = []
    for item in markets[:limit]:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "external_id": str(item.get("id") or item.get("conditionId") or item.get("slug") or ""),
            "question": str(item.get("question") or item.get("title") or item.get("slug") or "")[:240],
            "slug": item.get("slug"),
            "active": item.get("active"),
            "closed": item.get("closed"),
            "end_date": item.get("endDate") or item.get("end_date_iso"),
            "volume": item.get("volume") or item.get("volumeNum"),
            "liquidity": item.get("liquidity") or item.get("liquidityNum"),
            "url": item.get("url") or (f"https://polymarket.com/event/{item.get('slug')}" if item.get("slug") else None),
        })
    return {
        "source": "polymarket_gamma",
        "mode": "read_only",
        "ok": True,
        "notice": "Read-only public market discovery. NetCoin Labs trading stays separate and play-money only.",
        "markets": normalized,
    }
