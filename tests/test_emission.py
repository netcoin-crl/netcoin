"""Tests for NetCoin's deterministic 20% reward-reduction schedule."""
from pathlib import Path

import pytest

from netcoin import emission
from netcoin.chain import Blockchain
from netcoin.params import (
    COIN,
    INITIAL_SUBSIDY,
    LEGACY_NRE_ACTIVATION_HEIGHT,
    LEGACY_NRE_BASE_SUBSIDY,
    REWARD_REDUCTION_INTERVAL,
    REWARD_SCHEDULE_ACTIVATION_HEIGHT,
)
from netcoin.wallet import Wallet


EVEN_HASH = "00" * 32


def test_is_active_gates_on_new_activation_height():
    assert not emission.is_active(REWARD_SCHEDULE_ACTIVATION_HEIGHT - 1)
    assert emission.is_active(REWARD_SCHEDULE_ACTIVATION_HEIGHT)
    assert emission.is_active(REWARD_REDUCTION_INTERVAL)


def test_20_percent_reward_schedule_math():
    base = 50 * COIN
    assert emission.emission_subsidy(0) == base
    assert emission.emission_subsidy(REWARD_REDUCTION_INTERVAL - 1) == base
    cut1 = base * 4 // 5
    cut2 = cut1 * 4 // 5
    cut3 = cut2 * 4 // 5
    assert emission.emission_subsidy(REWARD_REDUCTION_INTERVAL) == cut1          # 40 NET
    assert emission.emission_subsidy(REWARD_REDUCTION_INTERVAL * 2) == cut2      # 32 NET
    assert emission.emission_subsidy(REWARD_REDUCTION_INTERVAL * 3) == cut3      # 25.6 NET


def test_next_reduction_height():
    assert emission.next_reduction_height(0) == REWARD_REDUCTION_INTERVAL
    assert emission.next_reduction_height(REWARD_REDUCTION_INTERVAL - 1) == REWARD_REDUCTION_INTERVAL
    assert emission.next_reduction_height(REWARD_REDUCTION_INTERVAL) == REWARD_REDUCTION_INTERVAL * 2


def test_negative_height_rejected_by_pure_helpers():
    with pytest.raises(ValueError):
        emission.emission_subsidy(-1)
    with pytest.raises(ValueError):
        emission.next_reduction_height(-1)


def test_legacy_random_window_preserved_for_existing_live_blocks():
    # Height 1,000 was already activated on the public testnet before this
    # deterministic schedule was chosen. Year zero of that legacy window is flat
    # 15 NET and does not need historical hash sampling.
    assert emission.is_legacy_random_window(LEGACY_NRE_ACTIVATION_HEIGHT)
    assert emission.legacy_random_emission_subsidy(LEGACY_NRE_ACTIVATION_HEIGHT, lambda h: EVEN_HASH) == LEGACY_NRE_BASE_SUBSIDY
    assert not emission.is_legacy_random_window(REWARD_SCHEDULE_ACTIVATION_HEIGHT)


def test_live_chain_uses_legacy_window_then_new_schedule(tmp_path: Path):
    wallet = Wallet.create()
    chain = Blockchain(tmp_path / "schedule")
    for _ in range(3):
        chain.mine_block(wallet.address)
    assert chain.subsidy(0) == INITIAL_SUBSIDY == 50 * COIN
    assert chain.subsidy(LEGACY_NRE_ACTIVATION_HEIGHT) == 15 * COIN
    assert chain.subsidy(REWARD_SCHEDULE_ACTIVATION_HEIGHT) == 50 * COIN
    assert chain.subsidy(REWARD_REDUCTION_INTERVAL) == 40 * COIN
