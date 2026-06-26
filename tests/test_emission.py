"""Tests for the random-emission schedule (netcoin.emission).

The live activation height is far in the future, so the schedule is exercised
here against the pure module with small, monkeypatched parameters and a synthetic
`hash_at`. A final test confirms the live chain's legacy halving path is
unchanged below activation (i.e. the change is additive).
"""
from pathlib import Path

import pytest

from netcoin import emission
from netcoin.chain import Blockchain
from netcoin.params import COIN, INITIAL_SUBSIDY
from netcoin.wallet import Wallet

EVEN_HASH = "00" * 32           # int(...,16) == 0 -> even
ODD_HASH = "00" * 31 + "01"     # int(...,16) == 1 -> odd


@pytest.fixture
def small_params(monkeypatch):
    """Tractable emission parameters for testing."""
    monkeypatch.setattr(emission, "EMISSION_ACTIVATION_HEIGHT", 10)
    monkeypatch.setattr(emission, "EMISSION_YEAR_BLOCKS", 20)
    monkeypatch.setattr(emission, "EMISSION_SEED_BLOCKS", 2)
    monkeypatch.setattr(emission, "EMISSION_SAMPLE_SIZE", 8)
    monkeypatch.setattr(emission, "EMISSION_EVEN_THRESHOLD", 5)
    monkeypatch.setattr(emission, "EMISSION_DRY_YEAR_LIMIT", 3)
    monkeypatch.setattr(emission, "EMISSION_BASE_SUBSIDY", 15 * COIN)
    return None


def hash_at_all(parity_hash):
    """A hash_at where every block has the given parity hash."""
    return lambda h: parity_hash


def test_is_active_gates_on_activation_height(small_params):
    assert not emission.is_active(9)
    assert emission.is_active(10)
    assert emission.is_active(10_000)


def test_year_zero_is_flat_base(small_params):
    hash_at = hash_at_all(EVEN_HASH)
    base = 15 * COIN
    # Whole of year 0 (heights 10..29) pays the base reward.
    assert emission.emission_subsidy(10, hash_at) == base
    assert emission.emission_subsidy(29, hash_at) == base


def test_all_even_prior_year_triggers_cuts(small_params):
    """Every prior year all-even -> every year market-cuts. Verifies cut math and
    the seed-window carryover (first SEED_BLOCKS of a year use the prior rate)."""
    hash_at = hash_at_all(EVEN_HASH)
    base = 15 * COIN
    cut1 = base * 9 // 10
    cut2 = cut1 * 9 // 10

    # Year 1 (heights 30..49). Seed window = 30..31 carries year-0 rate (base).
    assert emission.emission_subsidy(30, hash_at) == base
    assert emission.emission_subsidy(31, hash_at) == base
    # After the seed window, year 1's cut applies.
    assert emission.emission_subsidy(32, hash_at) == cut1
    assert emission.emission_subsidy(49, hash_at) == cut1

    # Year 2 (heights 50..69). Seed window = 50..51 carries year-1 rate (cut1).
    assert emission.emission_subsidy(50, hash_at) == cut1
    assert emission.emission_subsidy(52, hash_at) == cut2


def test_all_odd_prior_year_no_market_cut(small_params):
    """All-odd prior year -> 0 even samples -> no market cut for the first years."""
    hash_at = hash_at_all(ODD_HASH)
    base = 15 * COIN
    # Years 1..3 see no cut (below the dry-year limit), so reward stays at base.
    assert emission.emission_subsidy(32, hash_at) == base   # year 1, post-seed
    assert emission.emission_subsidy(52, hash_at) == base   # year 2, post-seed
    assert emission.emission_subsidy(72, hash_at) == base   # year 3, post-seed


def test_dry_year_safety_forces_cut(small_params):
    """After EMISSION_DRY_YEAR_LIMIT (3) consecutive no-cut years, year 4 forces a cut."""
    hash_at = hash_at_all(ODD_HASH)
    base = 15 * COIN
    # Year 4 (heights 90..109), post-seed (offset >= 2 -> height >= 92): forced cut.
    assert emission.emission_subsidy(92, hash_at) == base * 9 // 10
    # Year 5 resets the streak (a cut just happened) -> back to no cut.
    assert emission.emission_subsidy(112, hash_at) == base * 9 // 10  # carries year-4 cut


def test_deterministic(small_params):
    hash_at = hash_at_all(EVEN_HASH)
    a = emission.emission_subsidy(52, hash_at)
    b = emission.emission_subsidy(52, hash_at)
    assert a == b


def test_below_activation_raises(small_params):
    with pytest.raises(ValueError):
        emission.emission_subsidy(9, hash_at_all(EVEN_HASH))


def test_live_chain_legacy_subsidy_unchanged(tmp_path: Path):
    """The live activation height is far ahead of any mined height, so the legacy
    halving subsidy is unchanged — the change is additive."""
    wallet = Wallet.create()
    chain = Blockchain(tmp_path / "legacy")
    for _ in range(3):
        chain.mine_block(wallet.address)
    assert chain.subsidy(0) == INITIAL_SUBSIDY == 50 * COIN
    assert chain.subsidy(1) == 50 * COIN
    assert not emission.is_active(chain.chain[-1].header.height)
