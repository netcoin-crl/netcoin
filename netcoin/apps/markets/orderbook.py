"""Order book helpers for Polymarket-style CLOB views."""

from __future__ import annotations

from typing import Any


def aggregate_depth(levels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cumulative = 0
    result = []
    for level in levels:
        cumulative += int(level.get("quantity", 0) or 0)
        row = dict(level)
        row["cumulative_quantity"] = cumulative
        result.append(row)
    return result


def depth_chart_snapshot(clob: dict[str, Any]) -> dict[str, Any]:
    books = {}
    for outcome_id, book in clob.get("books", {}).items():
        books[outcome_id] = {
            "bids": aggregate_depth(book.get("bids", [])),
            "asks": aggregate_depth(book.get("asks", [])),
            "midpoint": book.get("midpoint"),
            "spread": book.get("spread"),
        }
    return {"market_id": clob.get("market_id"), "books": books}
