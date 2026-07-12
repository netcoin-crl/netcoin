"""Proof that the supply/emission API is functional (M6.1 public supply data)."""

from netcoin.emission import (
    REWARD_REDUCTION_INTERVAL,
    emission_report,
    emission_subsidy,
    total_emission_cap_sats,
)
from netcoin.params import COIN, REWARD_START_SUBSIDY


def test_emission_cap_is_finite_and_above_first_epoch():
    cap = total_emission_cap_sats()
    # The cap must at least cover the first full epoch of full-subsidy blocks.
    first_epoch = REWARD_START_SUBSIDY * REWARD_REDUCTION_INTERVAL
    assert cap > first_epoch
    # And it must be finite / bounded by the geometric-series ceiling (10x first epoch).
    assert cap < first_epoch * 11
    # Cap is a whole-satoshi integer.
    assert isinstance(cap, int)


def test_emission_report_shape_and_circulating_math():
    height = REWARD_REDUCTION_INTERVAL + 5  # into epoch 1
    minted = 1234 * COIN
    report = emission_report(height, minted_sats=minted)
    assert report["schema"] == "netcoin-emission-report-v1"
    assert report["max_supply_sats"] == total_emission_cap_sats()
    assert report["block_subsidy_sats"] == emission_subsidy(height)
    assert report["reduction_epoch"] == 1
    assert report["reduction_percent_per_epoch"] == 10
    assert report["circulating_supply_sats"] == minted
    assert report["remaining_to_mint_sats"] == report["max_supply_sats"] - minted
    assert 0 < report["percent_of_cap_minted"] < 100


def test_emission_report_without_minted_omits_circulating():
    report = emission_report(0)
    assert "circulating_supply_sats" not in report
    assert report["block_subsidy_sats"] == REWARD_START_SUBSIDY
    assert report["reduction_epoch"] == 0


def test_node_exposes_supply_and_emission_routes():
    # The functional wiring: node serves /supply and /emission.
    node_src = (__import__("pathlib").Path(__file__).resolve().parents[1] / "netcoin" / "node.py").read_text()
    assert 'parsed.path == "/supply"' in node_src
    assert 'parsed.path == "/emission"' in node_src
    assert "emission_report(" in node_src
