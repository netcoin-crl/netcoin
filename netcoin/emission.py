"""NetCoin deterministic reward schedule.

The live chain previously activated a short testnet-only random-emission window at
height 1,000. To keep already-mined blocks valid, that compatibility window is
left intact until ``REWARD_SCHEDULE_ACTIVATION_HEIGHT``. From that activation
height onward, NetCoin uses the simple public schedule:

* 50 NET starting subsidy.
* Reward event every 265,000 blocks.
* Each event reduces the reward by 10% (multiply by 9/10, integer sat floor).

The first 10% reduction is at absolute height 265,000, so the public countdown is
easy to understand even though the deterministic schedule is activation-gated for
safe upgrade rollout.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from .params import (
    COIN,
    LEGACY_NRE_ACTIVATION_HEIGHT,
    LEGACY_NRE_BASE_SUBSIDY,
    LEGACY_NRE_CUT_DENOMINATOR,
    LEGACY_NRE_CUT_NUMERATOR,
    LEGACY_NRE_DRY_YEAR_LIMIT,
    LEGACY_NRE_EVEN_THRESHOLD,
    LEGACY_NRE_SAMPLE_SIZE,
    LEGACY_NRE_SEED_BLOCKS,
    LEGACY_NRE_YEAR_BLOCKS,
    REWARD_REDUCTION_DENOMINATOR,
    REWARD_REDUCTION_INTERVAL,
    REWARD_REDUCTION_NUMERATOR,
    REWARD_SCHEDULE_ACTIVATION_HEIGHT,
    REWARD_START_SUBSIDY,
)

HashAt = Callable[[int], str]


def is_active(height: int) -> bool:
    """True when the new deterministic 10% reduction schedule governs height."""
    return height >= REWARD_SCHEDULE_ACTIVATION_HEIGHT


def is_legacy_random_window(height: int) -> bool:
    """True for the already-activated legacy NRE compatibility window."""
    return LEGACY_NRE_ACTIVATION_HEIGHT <= height < REWARD_SCHEDULE_ACTIVATION_HEIGHT


def reduction_epoch(height: int) -> int:
    """Absolute 265,000-block reward epoch for ``height``."""
    if height < 0:
        raise ValueError("height cannot be negative")
    return height // REWARD_REDUCTION_INTERVAL


def next_reduction_height(height: int) -> int:
    """Next absolute height where the 10% reward reduction begins."""
    if height < 0:
        raise ValueError("height cannot be negative")
    return (height // REWARD_REDUCTION_INTERVAL + 1) * REWARD_REDUCTION_INTERVAL


def emission_subsidy(height: int) -> int:
    """Block subsidy under the new deterministic 10% reduction schedule.

    Formula: ``50 NET * (9/10) ** floor(height / 265_000)`` with integer-satoshi
    flooring after each event.
    """
    if height < 0:
        raise ValueError("height cannot be negative")
    subsidy = REWARD_START_SUBSIDY
    for _ in range(reduction_epoch(height)):
        subsidy = subsidy * REWARD_REDUCTION_NUMERATOR // REWARD_REDUCTION_DENOMINATOR
    return subsidy


def total_emission_cap_sats() -> int:
    """Deterministic-schedule maximum supply in satoshis.

    Sums ``REWARD_REDUCTION_INTERVAL`` blocks per epoch at each epoch's
    integer-satoshi subsidy until the flooring reduction drives the subsidy to
    zero. This converges (geometric 0.9 decay with satoshi flooring), giving a
    finite, deterministic hard cap independent of chain state.
    """
    subsidy = REWARD_START_SUBSIDY
    total = 0
    while subsidy > 0:
        total += subsidy * REWARD_REDUCTION_INTERVAL
        subsidy = subsidy * REWARD_REDUCTION_NUMERATOR // REWARD_REDUCTION_DENOMINATOR
    return total


def emission_report(height: int, minted_sats: int | None = None) -> dict[str, Any]:
    """Public supply/emission snapshot for the supply API.

    ``minted_sats`` (actual coins minted so far, from chain state) is optional;
    when supplied the report includes circulating supply and percent-of-cap.
    All amounts are satoshis; callers format to NET as needed.
    """
    if height < 0:
        raise ValueError("height cannot be negative")
    cap = total_emission_cap_sats()
    report: dict[str, Any] = {
        "schema": "netcoin-emission-report-v1",
        "height": height,
        "max_supply_sats": cap,
        "block_subsidy_sats": emission_subsidy(height),
        "reduction_epoch": reduction_epoch(height),
        "next_reduction_height": next_reduction_height(height),
        "reduction_interval": REWARD_REDUCTION_INTERVAL,
        "reduction_percent_per_epoch": 100
        * (REWARD_REDUCTION_DENOMINATOR - REWARD_REDUCTION_NUMERATOR)
        // REWARD_REDUCTION_DENOMINATOR,
    }
    if minted_sats is not None:
        if minted_sats < 0:
            raise ValueError("minted_sats cannot be negative")
        report["circulating_supply_sats"] = minted_sats
        report["remaining_to_mint_sats"] = max(0, cap - minted_sats)
        report["percent_of_cap_minted"] = round(100.0 * minted_sats / cap, 6) if cap else 0.0
    return report


# ---------------------------------------------------------------------------
# Legacy NRE compatibility only for already-mined public-testnet blocks between
# heights 1,000 and the deterministic schedule activation height. Do not use for
# new economic policy after activation.


def _hash_is_even(block_hash: str) -> bool:
    return int(block_hash, 16) % 2 == 0


def _legacy_year_seed(year: int, hash_at: HashAt) -> bytes:
    start = LEGACY_NRE_ACTIVATION_HEIGHT + year * LEGACY_NRE_YEAR_BLOCKS
    h = hashlib.sha256()
    for i in range(LEGACY_NRE_SEED_BLOCKS):
        h.update(bytes.fromhex(hash_at(start + i)))
    return h.digest()


def _legacy_sampled_even_count(year: int, hash_at: HashAt) -> int:
    seed = _legacy_year_seed(year, hash_at)
    prev_year_start = LEGACY_NRE_ACTIVATION_HEIGHT + (year - 1) * LEGACY_NRE_YEAR_BLOCKS
    even = 0
    for n in range(LEGACY_NRE_SAMPLE_SIZE):
        draw = hashlib.sha256(seed + n.to_bytes(4, "big")).digest()
        idx = int.from_bytes(draw[:8], "big") % LEGACY_NRE_YEAR_BLOCKS
        if _hash_is_even(hash_at(prev_year_start + idx)):
            even += 1
    return even


def _legacy_cut_for_year(year: int, hash_at: HashAt, history: list[bool]) -> bool:
    market_cut = _legacy_sampled_even_count(year, hash_at) >= LEGACY_NRE_EVEN_THRESHOLD
    if market_cut:
        return True
    return len(history) >= LEGACY_NRE_DRY_YEAR_LIMIT and not any(history[-LEGACY_NRE_DRY_YEAR_LIMIT:])


def _legacy_cut_history(up_to_year: int, hash_at: HashAt) -> list[bool]:
    history: list[bool] = []
    for year in range(1, up_to_year + 1):
        history.append(_legacy_cut_for_year(year, hash_at, history))
    return history


def _legacy_subsidy_after_cuts(num_cuts: int) -> int:
    subsidy = LEGACY_NRE_BASE_SUBSIDY
    for _ in range(num_cuts):
        subsidy = subsidy * LEGACY_NRE_CUT_NUMERATOR // LEGACY_NRE_CUT_DENOMINATOR
    return subsidy


def legacy_random_emission_subsidy(height: int, hash_at: HashAt) -> int:
    """Old random-emission subsidy kept only so current live blocks validate."""
    if not is_legacy_random_window(height):
        raise ValueError("legacy_random_emission_subsidy called outside compatibility window")
    offset = height - LEGACY_NRE_ACTIVATION_HEIGHT
    year = offset // LEGACY_NRE_YEAR_BLOCKS
    within_year = offset % LEGACY_NRE_YEAR_BLOCKS
    if year == 0:
        return LEGACY_NRE_BASE_SUBSIDY
    settle_year = year - 1 if within_year < LEGACY_NRE_SEED_BLOCKS else year
    num_cuts = sum(_legacy_cut_history(settle_year, hash_at))
    return _legacy_subsidy_after_cuts(num_cuts)


def reward_schedule_summary(height: int) -> dict[str, int | str]:
    """Small serializable summary for app-layer dashboards."""
    current = emission_subsidy(max(0, height))
    nxt = next_reduction_height(max(0, height))
    return {
        "schedule": "10_percent_reduction",
        "start_subsidy_sats": REWARD_START_SUBSIDY,
        "start_subsidy": REWARD_START_SUBSIDY // COIN,
        "interval_blocks": REWARD_REDUCTION_INTERVAL,
        "reduction_percent": 10,
        "activation_height": REWARD_SCHEDULE_ACTIVATION_HEIGHT,
        "next_reduction_height": nxt,
        "blocks_to_next_reduction": max(0, nxt - height),
        "current_subsidy_sats": current,
        "current_subsidy": current // COIN if current % COIN == 0 else current / COIN,
    }
