"""Spacing v2: activation-gated 5-minute target blocks (no chain reset)."""
from netcoin.params import (
    DIFFICULTY_ADJUSTMENT_INTERVAL,
    SPACING_V2_ACTIVATION_HEIGHT,
    TARGET_SPACING_SECONDS,
    TARGET_SPACING_V2_SECONDS,
    min_difficulty_gap_at,
    target_spacing_at,
    target_timespan_at,
)


def test_activation_height_is_a_retarget_boundary():
    # One retarget window straddles the transition; keeping the activation on a
    # boundary means every later window is measured purely under one schedule.
    assert SPACING_V2_ACTIVATION_HEIGHT % DIFFICULTY_ADJUSTMENT_INTERVAL == 0


def test_spacing_schedule_switches_exactly_at_activation():
    before = SPACING_V2_ACTIVATION_HEIGHT - 1
    at = SPACING_V2_ACTIVATION_HEIGHT
    assert target_spacing_at(0) == TARGET_SPACING_SECONDS == 120
    assert target_spacing_at(before) == TARGET_SPACING_SECONDS
    assert target_spacing_at(at) == TARGET_SPACING_V2_SECONDS == 300
    assert target_spacing_at(at + 1_000_000) == TARGET_SPACING_V2_SECONDS


def test_derived_schedules_follow_spacing():
    before = SPACING_V2_ACTIVATION_HEIGHT - 1
    at = SPACING_V2_ACTIVATION_HEIGHT
    assert target_timespan_at(before) == 120 * DIFFICULTY_ADJUSTMENT_INTERVAL
    assert target_timespan_at(at) == 300 * DIFFICULTY_ADJUSTMENT_INTERVAL
    # Lone-miner floor rule waits two target spacings before allowing the floor.
    assert min_difficulty_gap_at(before) == 240
    assert min_difficulty_gap_at(at) == 600


def test_historical_blocks_keep_original_rules():
    # The live public testnet (heights 1..~4,7xx) must validate unchanged.
    for height in (1, 1_000, 4_200, 4_745, SPACING_V2_ACTIVATION_HEIGHT - 1):
        assert target_spacing_at(height) == 120
        assert min_difficulty_gap_at(height) == 240
