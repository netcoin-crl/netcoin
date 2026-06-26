"""NetCoin Random Emission (NRE) — yearly random "cut" emission schedule.

This module is a *pure, deterministic* description of the random-emission
subsidy. It takes a `hash_at(height) -> str` accessor (the hex block hash at a
given height) so it can be tested in isolation and wired to the live chain by
`Blockchain.subsidy`.

Design (see docs/ECONOMICS_PLAN.md for the full rationale):

* Emission is divided into fixed-length **emission years** of
  ``EMISSION_YEAR_BLOCKS`` blocks, indexed ``k = 0, 1, 2, ...`` starting at
  ``EMISSION_ACTIVATION_HEIGHT`` (``A``). Year ``k`` covers heights
  ``[A + k*Y, A + (k+1)*Y)``.
* Year 0 pays the flat ``EMISSION_BASE_SUBSIDY`` (no prior year to sample).
* For each year ``k >= 1`` a **cut decision** is made:
    - A *delayed seed* is built from the first ``EMISSION_SEED_BLOCKS`` blocks of
      year ``k``. Using blocks from the *start of the new year* (not the end of
      the old one) removes any single last actor's ability to grind the outcome.
    - That seed deterministically samples ``EMISSION_SAMPLE_SIZE`` blocks from
      year ``k-1``. "Even" means **even hash** (``int(hash, 16) % 2 == 0``) — PoW
      hash parity is a genuine ~50/50 coin flip per block, unlike height parity
      which is deterministically 50% and carries no randomness.
    - If at least ``EMISSION_EVEN_THRESHOLD`` of the samples are even, the reward
      is cut 10% for year ``k``.
    - Safety: if there has been no cut for ``EMISSION_DRY_YEAR_LIMIT`` consecutive
      years, a cut is forced regardless of the sample.

Seed timing / no circular dependency: the seed for year ``k`` is only known once
year ``k``'s first ``EMISSION_SEED_BLOCKS`` blocks exist. Those seed-window blocks
are therefore paid at the *previous* settled rate (year ``k-1``); the year-``k``
cut only applies from block ``A + k*Y + EMISSION_SEED_BLOCKS`` onward. A block's
subsidy never depends on its own hash or on any later block, so validation is
well defined.
"""

from __future__ import annotations

import hashlib
from typing import Callable, List

from .params import (
    EMISSION_ACTIVATION_HEIGHT,
    EMISSION_BASE_SUBSIDY,
    EMISSION_CUT_DENOMINATOR,
    EMISSION_CUT_NUMERATOR,
    EMISSION_DRY_YEAR_LIMIT,
    EMISSION_EVEN_THRESHOLD,
    EMISSION_SAMPLE_SIZE,
    EMISSION_SEED_BLOCKS,
    EMISSION_YEAR_BLOCKS,
)

HashAt = Callable[[int], str]


def is_active(height: int) -> bool:
    """True if the random-emission schedule governs this height."""
    return height >= EMISSION_ACTIVATION_HEIGHT


def _hash_is_even(block_hash: str) -> bool:
    return int(block_hash, 16) % 2 == 0


def _year_seed(year: int, hash_at: HashAt) -> bytes:
    """Delayed seed for `year` (k>=1): the first EMISSION_SEED_BLOCKS blocks of it."""
    start = EMISSION_ACTIVATION_HEIGHT + year * EMISSION_YEAR_BLOCKS
    h = hashlib.sha256()
    for i in range(EMISSION_SEED_BLOCKS):
        h.update(bytes.fromhex(hash_at(start + i)))
    return h.digest()


def _sampled_even_count(year: int, hash_at: HashAt) -> int:
    """Count even-hash blocks among EMISSION_SAMPLE_SIZE samples of year `year-1`,
    chosen deterministically from year `year`'s delayed seed (with replacement)."""
    seed = _year_seed(year, hash_at)
    prev_year_start = EMISSION_ACTIVATION_HEIGHT + (year - 1) * EMISSION_YEAR_BLOCKS
    even = 0
    for n in range(EMISSION_SAMPLE_SIZE):
        draw = hashlib.sha256(seed + n.to_bytes(4, "big")).digest()
        idx = int.from_bytes(draw[:8], "big") % EMISSION_YEAR_BLOCKS
        if _hash_is_even(hash_at(prev_year_start + idx)):
            even += 1
    return even


def _cut_for_year(year: int, hash_at: HashAt, history: List[bool]) -> bool:
    """Whether year `year` (>=1) cuts the reward. `history` holds the cut bools for
    years 1..year-1 (in order)."""
    market_cut = _sampled_even_count(year, hash_at) >= EMISSION_EVEN_THRESHOLD
    if market_cut:
        return True
    # Safety: force a cut after EMISSION_DRY_YEAR_LIMIT consecutive no-cut years.
    if len(history) >= EMISSION_DRY_YEAR_LIMIT and not any(history[-EMISSION_DRY_YEAR_LIMIT:]):
        return True
    return False


def _cut_history(up_to_year: int, hash_at: HashAt) -> List[bool]:
    """Cut decisions for years 1..up_to_year (empty if up_to_year < 1)."""
    history: List[bool] = []
    for year in range(1, up_to_year + 1):
        history.append(_cut_for_year(year, hash_at, history))
    return history


def _subsidy_after_cuts(num_cuts: int) -> int:
    """Base reward after applying `num_cuts` sequential 10% cuts (integer floor)."""
    subsidy = EMISSION_BASE_SUBSIDY
    for _ in range(num_cuts):
        subsidy = subsidy * EMISSION_CUT_NUMERATOR // EMISSION_CUT_DENOMINATOR
    return subsidy


def emission_subsidy(height: int, hash_at: HashAt) -> int:
    """Block subsidy for `height` under the random-emission schedule.

    Only valid for `height >= EMISSION_ACTIVATION_HEIGHT` (the legacy halving
    schedule governs earlier heights). `hash_at` must return the hex block hash
    for any height strictly below `height`.
    """
    if not is_active(height):
        raise ValueError("emission_subsidy called below activation height")
    offset = height - EMISSION_ACTIVATION_HEIGHT
    year = offset // EMISSION_YEAR_BLOCKS
    within_year = offset % EMISSION_YEAR_BLOCKS

    if year == 0:
        # First emission year: flat base reward, no prior year to sample.
        return EMISSION_BASE_SUBSIDY

    # The seed window of a year is paid at the previous year's settled rate,
    # because this year's cut decision is not yet determined.
    settle_year = year - 1 if within_year < EMISSION_SEED_BLOCKS else year
    num_cuts = sum(_cut_history(settle_year, hash_at))
    return _subsidy_after_cuts(num_cuts)
