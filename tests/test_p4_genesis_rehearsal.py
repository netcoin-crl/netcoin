from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.block import Block, check_proof_of_work
from netcoin.params import ZERO_HASH
from tools.generate_genesis import build_genesis_block, generate_report, validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def load_example_manifest() -> dict:
    return json.loads((ROOT / "config" / "genesis_rehearsal_manifest.example.json").read_text(encoding="utf-8"))


def test_genesis_rehearsal_manifest_mines_valid_height_zero_block():
    manifest = load_example_manifest()
    report = generate_report(manifest, requested_network="regtest")
    block = Block.from_dict(report["block"])
    assert report["ok"] is True, report
    assert report["schema"] == "netcoin-genesis-rehearsal-report-v1"
    assert report["network"] == "regtest"
    assert report["header"]["height"] == 0
    assert report["header"]["previous_hash"] == ZERO_HASH
    assert report["header"]["merkle_root"] == block.header.merkle_root
    assert report["block_hash"] == block.hash()
    assert check_proof_of_work(block.header)
    assert report["mainnet_wired"] is False
    assert report["consensus_integrated"] is False
    assert report["writes_runtime_params"] is False


def test_genesis_rehearsal_hard_refuses_mainnet():
    manifest = {**load_example_manifest(), "network": "mainnet"}
    validation = validate_manifest(manifest, requested_network="mainnet")
    assert validation["ok"] is False
    assert any("hard-refuses mainnet" in issue for issue in validation["issues"])
    proc = subprocess.run(
        [sys.executable, "tools/generate_genesis.py", "--network", "mainnet", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "hard-refuses mainnet" in proc.stderr


def test_genesis_rehearsal_accepts_testnet_rehearsal_manifest():
    manifest = {
        **load_example_manifest(),
        "network": "testnet-rehearsal",
        "coinbase_message": "NetCoin testnet rehearsal genesis - not mainnet",
    }
    report = generate_report(manifest, requested_network="testnet-rehearsal")
    assert report["ok"] is True, report
    assert report["network"] == "testnet-rehearsal"
    assert report["header"]["height"] == 0
    assert report["mainnet_wired"] is False


def test_genesis_rehearsal_requires_network_match_and_ceremony_guard():
    manifest = load_example_manifest()
    mismatch = validate_manifest(manifest, requested_network="testnet-rehearsal")
    assert mismatch["ok"] is False
    assert any("network must match" in issue for issue in mismatch["issues"])

    unsafe = {**manifest, "ceremony": {"requires_nip_before_activation": False}}
    unsafe_result = validate_manifest(unsafe, requested_network="regtest")
    assert unsafe_result["ok"] is False
    assert any("requires_nip_before_activation" in issue for issue in unsafe_result["issues"])


def test_genesis_rehearsal_rejects_malformed_outputs():
    manifest = load_example_manifest()
    bad = {
        **manifest,
        "outputs": [{"name": "bad", "amount": 1}],
    }
    result = validate_manifest(bad, requested_network="regtest")
    assert result["ok"] is False
    assert any("requires address or script_pubkey" in issue for issue in result["issues"])

    malformed = {**manifest, "height": "zero", "bits": "floor"}
    malformed_result = validate_manifest(malformed, requested_network="regtest")
    assert malformed_result["ok"] is False
    assert any("height must be an integer" in issue for issue in malformed_result["issues"])
    assert any("bits must be an integer" in issue for issue in malformed_result["issues"])


def test_genesis_rehearsal_cli_writes_report_and_block(tmp_path: Path):
    out = tmp_path / "genesis-report.json"
    block_out = tmp_path / "genesis-block.json"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/generate_genesis.py",
            "--network",
            "regtest",
            "--out",
            str(out),
            "--block-out",
            str(block_out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    block = Block.from_dict(json.loads(block_out.read_text(encoding="utf-8")))
    assert payload["ok"] is True
    assert payload["block_hash"] == block.hash()


def test_genesis_rehearsal_docs_and_make_target_are_wired():
    docs = (ROOT / "docs" / "GENESIS_REHEARSAL.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    manifest = load_example_manifest()
    block = build_genesis_block(manifest, requested_network="regtest")
    assert "hard-refused" in docs or "hard-refuses" in docs
    assert "genesis-rehearsal-check" in makefile
    assert block.header.height == 0
