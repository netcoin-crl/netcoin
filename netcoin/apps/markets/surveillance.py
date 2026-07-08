"""Prediction-market surveillance helpers."""

from __future__ import annotations

from typing import Any


def liquidity_reward_score(book: dict[str, Any]) -> int:
    spread = int(book.get("spread_bps") or 10_000)
    depth = int(book.get("depth_quantity") or 0)
    return max(0, depth * max(0, 10_000 - spread) // 10_000)
