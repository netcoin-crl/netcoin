"""Wave 1.1 real multi-node localnet harness tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.run_localnet import Localnet, LocalnetConfig, LocalnetError, run_localnet


@pytest.mark.localnet
def test_run_localnet_harness_exercises_real_node_processes(tmp_path: Path):
    report = run_localnet(
        LocalnetConfig(
            nodes=3,
            bootstrap_blocks=101,
            relay_timeout=30,
            startup_timeout=30,
            root_dir=tmp_path / "localnet",
            keep_artifacts=True,
        )
    )
    assert report["ok"] is True, report
    assertions = report["assertions"]
    assert assertions["header_sync"]["height"] >= 101
    assert assertions["tx_relay"]["nodes_with_tx"] == 3
    assert assertions["pex_propagation"]["node0_peers"]
    assert assertions["compact_block_reconstruction"]["shortids"] >= 1
    assert assertions["reorg_resolution"]["converged_height"] >= 2
    assert assertions["restart_replay"]["height"] >= 102
    assert assertions["cleanup"]["node_processes_stopped"] is True


@pytest.mark.localnet
def test_run_localnet_cli_outputs_json_report(tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            "tools/run_localnet.py",
            "--nodes",
            "3",
            "--bootstrap-blocks",
            "101",
            "--relay-timeout",
            "30",
            "--startup-timeout",
            "30",
            "--root-dir",
            str(tmp_path / "cli-localnet"),
            "--keep-artifacts",
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert '"ok": true' in result.stdout
    assert '"reorg_resolution"' in result.stdout


def test_localnet_rejects_too_few_nodes(tmp_path: Path):
    with pytest.raises(LocalnetError, match="3 to 7"):
        Localnet(LocalnetConfig(nodes=2, root_dir=tmp_path))


def test_localnet_rejects_immature_bootstrap(tmp_path: Path):
    with pytest.raises(LocalnetError, match="bootstrap_blocks"):
        Localnet(LocalnetConfig(nodes=3, bootstrap_blocks=10, root_dir=tmp_path))
