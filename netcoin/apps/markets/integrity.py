"""Prediction-market integrity checks for operators and dispute reviewers."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any


def self_trade_report(market: dict[str, Any]) -> dict[str, Any]:
    """Detect trades where maker and taker resolve to the same trader id."""
    flagged = []
    for trade in market.get("trades", []):
        maker = str(trade.get("maker") or trade.get("maker_address") or trade.get("maker_trader") or "")
        taker = str(trade.get("taker") or trade.get("taker_address") or trade.get("taker_trader") or "")
        if maker and maker == taker:
            flagged.append(trade)
    return {
        "market_id": market.get("market_id"),
        "flagged_count": len(flagged),
        "flagged_trades": flagged,
        "ok": not flagged,
    }


def cancel_rate_report(market: dict[str, Any], *, high_cancel_ratio_bps: int = 8000) -> dict[str, Any]:
    """Estimate spoofing risk from per-trader cancellation rate."""
    per_trader: dict[str, Counter[str]] = defaultdict(Counter)
    for order in market.get("orders", []):
        trader = str(order.get("trader_address") or order.get("trader") or "unknown")
        status = str(order.get("status") or "unknown")
        per_trader[trader][status] += 1
    rows = []
    for trader, counts in per_trader.items():
        total = sum(counts.values())
        canceled = counts.get("canceled", 0) + counts.get("expired", 0)
        ratio_bps = 0 if total == 0 else canceled * 10_000 // total
        rows.append(
            {
                "trader": trader,
                "orders": total,
                "canceled_or_expired": canceled,
                "cancel_ratio_bps": ratio_bps,
                "flagged": ratio_bps >= int(high_cancel_ratio_bps) and total >= 5,
            }
        )
    rows.sort(key=lambda r: (-int(r["cancel_ratio_bps"]), r["trader"]))
    return {
        "market_id": market.get("market_id"),
        "flagged_count": sum(1 for r in rows if r["flagged"]),
        "traders": rows,
    }


def dispute_timeline(market: dict[str, Any]) -> dict[str, Any]:
    """Return a sorted dispute/evidence/resolution timeline."""
    items: list[dict[str, Any]] = []
    for ev in market.get("resolution_evidence", []) + market.get("evidence", []):
        if isinstance(ev, dict):
            items.append(
                {
                    "type": "evidence",
                    "timestamp": int(ev.get("timestamp") or ev.get("created_at") or 0),
                    "title": ev.get("title", ""),
                    "payload": ev,
                }
            )
    for dispute in market.get("disputes", []):
        if isinstance(dispute, dict):
            items.append(
                {
                    "type": "dispute",
                    "timestamp": int(dispute.get("timestamp") or dispute.get("created_at") or 0),
                    "title": dispute.get("comment", dispute.get("reason", "dispute")),
                    "payload": dispute,
                }
            )
    for event in market.get("audit_trail", []):
        if isinstance(event, dict) and str(event.get("event", "")).startswith(("resolve", "dispute", "evidence")):
            items.append(
                {
                    "type": "audit",
                    "timestamp": int(event.get("created_at") or 0),
                    "title": event.get("event", "audit"),
                    "payload": event,
                }
            )
    items.sort(key=lambda item: (item["timestamp"], item["type"], item["title"]))
    digest = hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"market_id": market.get("market_id"), "event_count": len(items), "timeline_hash": digest, "events": items}


def market_integrity_score(market: dict[str, Any]) -> dict[str, Any]:
    """Combine integrity checks into a simple operator score."""
    self_trade = self_trade_report(market)
    cancel_rate = cancel_rate_report(market)
    timeline = dispute_timeline(market)
    score = 100
    penalties: list[str] = []
    if self_trade["flagged_count"]:
        score -= min(40, 10 * int(self_trade["flagged_count"]))
        penalties.append("self_trading_detected")
    if cancel_rate["flagged_count"]:
        score -= min(30, 5 * int(cancel_rate["flagged_count"]))
        penalties.append("high_cancel_rate")
    if market.get("status") == "resolved" and not market.get("winning_outcome_id"):
        score -= 30
        penalties.append("resolved_without_winner")
    if market.get("status") in {"resolved", "settled"} and timeline["event_count"] == 0:
        score -= 10
        penalties.append("no_resolution_timeline")
    score = max(0, score)
    level = "low" if score >= 90 else "medium" if score >= 65 else "high" if score >= 40 else "critical"
    return {
        "market_id": market.get("market_id"),
        "score": score,
        "risk_level": level,
        "penalties": penalties,
        "self_trade": self_trade,
        "cancel_rate": cancel_rate,
        "timeline_hash": timeline["timeline_hash"],
    }
