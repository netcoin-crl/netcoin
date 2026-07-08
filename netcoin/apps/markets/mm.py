"""Market-maker quote planning tools for Labs markets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class QuotePlan:
    outcome_id: str
    bid_bps: int
    ask_bps: int
    quantity: int
    cancel_stale: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_quotes(
    market: dict[str, Any],
    *,
    fair_values_bps: dict[str, int] | None = None,
    spread_bps: int = 200,
    quantity: int = 10,
    max_exposure: int = 1000,
) -> dict[str, Any]:
    fair_values_bps = fair_values_bps or {}
    plans = []
    positions = market.get("positions", {})
    for outcome in market.get("outcomes", []):
        oid = outcome["outcome_id"]
        fair = int(fair_values_bps.get(oid, 5000))
        bid = max(1, fair - int(spread_bps) // 2)
        ask = min(9999, fair + int(spread_bps) // 2)
        exposure = sum(abs(int(pos.get(oid, 0) or 0)) for pos in positions.values() if isinstance(pos, dict))
        q = max(0, min(int(quantity), int(max_exposure) - exposure))
        if q > 0:
            plans.append(QuotePlan(outcome_id=oid, bid_bps=bid, ask_bps=ask, quantity=q).to_dict())
    return {
        "market_id": market.get("market_id"),
        "quote_count": len(plans),
        "quotes": plans,
        "spread_bps": int(spread_bps),
        "max_exposure": int(max_exposure),
    }


def quote_orders_from_plan(plan: dict[str, Any], trader: str) -> list[dict[str, Any]]:
    orders = []
    for quote in plan.get("quotes", []):
        orders.append(
            {
                "trader_address": trader,
                "allow_unverified_demo": str(trader).startswith("demo:"),
                "outcome_id": quote["outcome_id"],
                "side": "buy",
                "order_type": "limit",
                "price_bps": quote["bid_bps"],
                "quantity": quote["quantity"],
                "post_only": True,
            }
        )
        orders.append(
            {
                "trader_address": trader,
                "allow_unverified_demo": str(trader).startswith("demo:"),
                "outcome_id": quote["outcome_id"],
                "side": "sell",
                "order_type": "limit",
                "price_bps": quote["ask_bps"],
                "quantity": quote["quantity"],
                "post_only": True,
            }
        )
    return orders


def inventory_risk(market: dict[str, Any], trader: str, *, max_position: int = 1000) -> dict[str, Any]:
    positions = market.get("positions", {}).get(trader, {}) if isinstance(market.get("positions"), dict) else {}
    exposures = {k: int(v or 0) for k, v in positions.items()} if isinstance(positions, dict) else {}
    max_abs = max((abs(v) for v in exposures.values()), default=0)
    level = (
        "low"
        if max_abs < max_position * 0.4
        else "medium" if max_abs < max_position * 0.75 else "high" if max_abs <= max_position else "critical"
    )
    return {
        "trader": trader,
        "max_position": int(max_position),
        "max_abs_position": max_abs,
        "risk_level": level,
        "exposures": exposures,
    }


def rebalance_suggestions(
    market: dict[str, Any], trader: str, *, target_position: int = 0, max_order_quantity: int = 25
) -> dict[str, Any]:
    risk = inventory_risk(market, trader, max_position=max(1, abs(int(target_position)) + int(max_order_quantity)))
    suggestions = []
    for outcome_id, qty in risk["exposures"].items():
        delta = int(target_position) - int(qty)
        if delta == 0:
            continue
        suggestions.append(
            {
                "outcome_id": outcome_id,
                "side": "buy" if delta > 0 else "sell",
                "quantity": min(abs(delta), int(max_order_quantity)),
                "reason": "rebalance_inventory",
            }
        )
    return {"trader": trader, "suggestion_count": len(suggestions), "suggestions": suggestions, "inventory_risk": risk}
