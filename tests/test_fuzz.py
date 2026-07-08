"""Deterministic fuzz runner for parsers and public node endpoints."""

import argparse
import json

import pytest

from netcoin import cli
from netcoin.fuzz import TARGETS, FuzzConfig, FuzzError, run_fuzz


def test_fuzz_runner_all_targets_survive():
    report = run_fuzz(FuzzConfig(target="all", iterations=25, seed=20260622, max_bytes=64))
    assert report["ok"] is True
    assert report["total_cases"] == 25 * len(TARGETS)
    assert {item["target"] for item in report["targets"]} == set(TARGETS)
    assert all(item["cases"] == 25 for item in report["targets"])


def test_fuzz_runner_rejects_unknown_target():
    with pytest.raises(FuzzError, match="unknown fuzz target"):
        run_fuzz(FuzzConfig(target="bogus", iterations=1))


def test_cli_fuzz_outputs_json(capsys):
    args = argparse.Namespace(target="rawtx", iterations=5, seed=7, max_bytes=16)
    cli.cmd_fuzz(args)
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["total_cases"] == 5
    assert report["targets"][0]["target"] == "rawtx"
