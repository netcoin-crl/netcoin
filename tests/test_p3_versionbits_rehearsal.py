from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from netcoin.versionbits import (
    ACTIVE,
    ENV_ENABLE_REHEARSAL,
    LOCKED_IN,
    STARTED,
    VersionBitsDeployment,
    VersionBitsRehearsalConfig,
    enforce_rehearsal_rule,
    evaluate_rehearsal_chain,
    extract_block_versions,
    load_rehearsal_config,
)
from tools.run_versionbits_rehearsal import run_localnet_rehearsal

ROOT = Path(__file__).resolve().parents[1]


def small_deployment() -> VersionBitsDeployment:
    return VersionBitsDeployment(
        name="small",
        bit=0,
        start_height=0,
        timeout_height=20,
        period=2,
        threshold=2,
    )


def test_rehearsal_config_hard_refuses_mainnet():
    config = VersionBitsRehearsalConfig(network="mainnet", deployment=small_deployment(), enabled=True)
    with pytest.raises(ValueError, match="hard-refuses mainnet"):
        config.require_safe()


def test_rehearsal_chain_reads_real_block_version_shapes_and_reaches_active():
    config = VersionBitsRehearsalConfig(network="regtest", deployment=small_deployment(), enabled=True)
    blocks = [{"header": {"version": 1}} for _ in range(6)]
    versions = extract_block_versions(blocks)
    report = evaluate_rehearsal_chain(config, versions)
    assert report["ok"] is True, report
    assert [period["state"] for period in report["periods"]] == [STARTED, LOCKED_IN, ACTIVE]
    assert report["final_state"] == ACTIVE
    assert report["mainnet_wired"] is False


def test_active_rehearsal_rule_rejects_missing_signal_bit():
    config = VersionBitsRehearsalConfig(network="regtest", deployment=small_deployment(), enabled=True)
    result = enforce_rehearsal_rule(config, state=ACTIVE, candidate_version=0)
    assert result["ok"] is False
    assert result["enforced"] is True


def test_disabled_rehearsal_reports_issue_without_consensus_integration():
    config = VersionBitsRehearsalConfig(network="regtest", deployment=small_deployment(), enabled=False)
    report = evaluate_rehearsal_chain(config, [1, 1])
    assert report["ok"] is False
    assert ENV_ENABLE_REHEARSAL in report["issues"][0]
    assert report["consensus_integrated"] is False


def test_rehearsal_config_loader_uses_example_and_env(tmp_path: Path):
    payload = {
        "network": "testnet-rehearsal",
        "deployment": small_deployment().__dict__,
    }
    path = tmp_path / "versionbits.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    config = load_rehearsal_config(path, env={ENV_ENABLE_REHEARSAL: "1"})
    assert config.enabled is True
    assert config.network == "testnet-rehearsal"


def test_versionbits_docs_and_make_target_are_wired():
    docs = (ROOT / "docs" / "VERSIONBITS_REHEARSAL.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    config = (ROOT / "config" / "versionbits_rehearsal.example.json").read_text(encoding="utf-8")
    source = (ROOT / "netcoin" / "versionbits.py").read_text(encoding="utf-8")
    assert "mainnet" in docs and "hard-fail" in docs
    assert "versionbits-rehearsal-check" in makefile
    assert "trivial-active-signal-rehearsal" in config
    assert "mainnet_wired" in source


@pytest.mark.localnet
def test_versionbits_localnet_rehearsal_runs(tmp_path: Path):
    config = VersionBitsRehearsalConfig(network="regtest", deployment=small_deployment(), enabled=True)
    report = run_localnet_rehearsal(
        config,
        root_dir=tmp_path / "vb",
        keep_artifacts=True,
        startup_timeout=30,
        relay_timeout=30,
    )
    assert report["ok"] is True, report
    assert report["evaluation"]["final_state"] == ACTIVE
    assert all(version & 1 for version in report["mined_versions"])


@pytest.mark.localnet
def test_versionbits_rehearsal_cli_outputs_report(tmp_path: Path):
    out = tmp_path / "vb-report.json"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_versionbits_rehearsal.py",
            "--root-dir",
            str(tmp_path / "cli-vb"),
            "--keep-artifacts",
            "--startup-timeout",
            "30",
            "--relay-timeout",
            "30",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
        env={**os.environ, ENV_ENABLE_REHEARSAL: "1"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["schema"] == "netcoin-versionbits-localnet-rehearsal-v1"
