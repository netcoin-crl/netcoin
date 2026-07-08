"""Matching-engine constants/helpers."""

from __future__ import annotations


def maker_taker_fee_sats(notional_sats: int, maker_fee_bps: int = 0, taker_fee_bps: int = 0) -> tuple[int, int]:
    return int(notional_sats) * int(maker_fee_bps) // 10_000, int(notional_sats) * int(taker_fee_bps) // 10_000
