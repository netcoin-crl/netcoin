from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.run_chaos_drill import ChaosConfig, ChaosDrillError, run_chaos_drill

ROOT = Path(__file__).resolve().parents[1]


def test_chaos_drill_rejects_too_few_nodes():
    with pytest.raises(ChaosDrillError, match="3 to 7"):
        run_chaos_drill(ChaosConfig(nodes=2))


def test_chaos_drill_source_is_local_only():
    source = (ROOT / "tools" / "run_chaos_drill.py").read_text(encoding="utf-8")
    assert "http://127.0.0.1:" in source
    assert "refusing non-local node URL" in source
    for forbidden in ["seed1.netcoin.online", "ssh ", "scp ", "systemctl", "sudo ", "deploy_seed.sh"]:
        assert forbidden not in source


def test_chaos_drill_docs_and_make_target_are_wired():
    doc = (ROOT / "docs" / "CHAOS_DRILL.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "tools/run_chaos_drill.py" in doc
    assert "local-only" in doc
    assert "chaos-drill-check" in makefile


@pytest.mark.localnet
def test_chaos_drill_runs_against_real_localnet_processes(tmp_path: Path):
    report = run_chaos_drill(
        ChaosConfig(
            nodes=3,
            startup_timeout=30,
            recovery_timeout=30,
            root_dir=tmp_path / "chaos",
            keep_artifacts=True,
        )
    )
    assert report["ok"] is True, report
    drill_ids = {item["id"] for item in report["drills"]}
    assert {
        "kill-restart-resync",
        "mempool-file-corruption",
        "dead-peer-relay-drain",
        "partition-rejoin",
    } <= drill_ids
    partition = next(item for item in report["drills"] if item["id"] == "partition-rejoin")
    assert partition["competing_tips"] >= 2
    assert partition["recovered_height"] >= 2


@pytest.mark.localnet
def test_chaos_drill_cli_outputs_json(tmp_path: Path):
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_chaos_drill.py",
            "--nodes",
            "3",
            "--startup-timeout",
            "30",
            "--recovery-timeout",
            "30",
            "--root-dir",
            str(tmp_path / "cli-chaos"),
            "--keep-artifacts",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["schema"] == "netcoin-chaos-drill-v1"
