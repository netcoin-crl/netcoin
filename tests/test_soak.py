"""Local multi-node soak/stress harness."""

import argparse
import json
from pathlib import Path

import pytest

from netcoin import cli
from netcoin.soak import SoakConfig, SoakError, run_soak


def test_run_soak_converges_two_nodes(tmp_path: Path):
    report = run_soak(
        SoakConfig(nodes=2, rounds=1, transactions_per_round=1, bootstrap_blocks=101),
        base_dir=tmp_path / "soak",
    )
    assert report["ok"] is True
    assert report["nodes"] == 2
    assert report["transactions_created"] == 1
    assert report["blocks_mined"] == 102
    assert len({(tip["height"], tip["tip_hash"]) for tip in report["tips"]}) == 1
    assert report["relay_queues"] == [0, 0]


def test_run_soak_rejects_immature_bootstrap(tmp_path: Path):
    with pytest.raises(SoakError, match="bootstrap blocks"):
        run_soak(SoakConfig(nodes=2, bootstrap_blocks=10), base_dir=tmp_path / "bad")


def test_cli_soak_outputs_json(tmp_path: Path, capsys):
    args = argparse.Namespace(
        nodes=2,
        rounds=1,
        transactions_per_round=0,
        bootstrap_blocks=101,
        amount="1",
        fee="0.01",
        dir=str(tmp_path / "cli-soak"),
    )
    cli.cmd_soak(args)
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["transactions_created"] == 0
    assert len({tip["tip_hash"] for tip in report["tips"]}) == 1
