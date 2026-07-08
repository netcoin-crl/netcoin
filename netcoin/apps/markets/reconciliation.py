"""Settlement reconciliation for prediction markets."""

from __future__ import annotations

from typing import Any

from ...tx import sats_to_amount


def settlement_reconciliation(market: dict[str, Any]) -> dict[str, Any]:
    winning = market.get("winning_outcome_id")
    unit = int(market.get("unit_payout_sats", 100_000_000) or 100_000_000)
    rows = []
    total_claimable = 0
    negative_balances = []
    for trader, positions in market.get("positions", {}).items():
        if not isinstance(positions, dict):
            continue
        win_qty = int(positions.get(winning, 0) or 0) if winning else 0
        claimable = max(0, win_qty) * unit
        total_claimable += claimable
        wallet = market.get("wallets", {}).get(trader, {})
        if int(wallet.get("balance_sats", 0) or 0) < 0:
            negative_balances.append(trader)
        rows.append(
            {
                "trader_id": trader,
                "winning_quantity": win_qty,
                "claimable_sats": claimable,
                "claimable": sats_to_amount(claimable),
            }
        )
    locked = sum(int(w.get("reserved_sats", 0) or 0) for w in market.get("wallets", {}).values() if isinstance(w, dict))
    return {
        "market_id": market.get("market_id"),
        "status": market.get("status"),
        "winning_outcome_id": winning,
        "unit_payout_sats": unit,
        "total_claimable_sats": total_claimable,
        "total_claimable": sats_to_amount(total_claimable),
        "reserved_sats": locked,
        "reserved": sats_to_amount(locked),
        "negative_balances": negative_balances,
        "ok": not negative_balances and market.get("status") in {"resolved", "settled", "disputed"},
        "rows": rows,
    }


def settlement_audit_report(market: dict[str, Any]) -> dict[str, Any]:
    """Return a stricter accounting checklist for a resolved/settling market."""
    report = settlement_reconciliation(market)
    checks = [
        {"name": "terminal_or_disputed_state", "ok": market.get("status") in {"resolved", "settled", "disputed"}},
        {"name": "winning_outcome_selected", "ok": bool(market.get("winning_outcome_id"))},
        {"name": "no_negative_balances", "ok": not report.get("negative_balances")},
        {"name": "claimable_not_negative", "ok": int(report.get("total_claimable_sats", 0)) >= 0},
    ]
    report["checks"] = checks
    report["ok"] = all(c["ok"] for c in checks)
    return report
