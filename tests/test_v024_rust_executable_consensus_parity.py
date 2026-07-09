from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import run_parity_suite

ROOT = Path(__file__).resolve().parents[1]


def test_v024_expands_vectors_and_project_version() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 5
    assert report["total"] >= 66
    assert report["lanes"]["consensus"]["passed"] >= 30
    assert vectors["generated_by"] in {
        "netcoin-v0.24-rust-executable-consensus-parity",
        "netcoin-v0.25-rust-mempool-parity",
        "netcoin-v0.26-rust-wallet-core-parity",
        "netcoin-v0.31-rust-ts-full-parity-expansion",
    }
    assert vectors["consensus"]["vector_set"] == "consensus-executable-vectors-v4"
    assert vectors["consensus"]["valid_cases"] >= 16
    assert vectors["consensus"]["invalid_cases"] >= 14


def test_v024_rust_executable_files_and_symbols_exist() -> None:
    lib = (ROOT / "core-rs/crates/consensus/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/consensus/src/bin/netcoin-consensus-parity.rs").read_text(encoding="utf-8")
    tool = (ROOT / "tools/run_rust_consensus_parity.py").read_text(encoding="utf-8")
    for symbol in ["run_consensus_case", "run_consensus_parity_vectors", "consensus_actual_for_case"]:
        assert symbol in lib
    assert "run_consensus_parity_vectors" in binary
    assert "serde_json::to_string_pretty" in binary
    assert "cargo" in tool
    assert "_compare_with_rust" in tool


def test_v024_source_only_rust_comparison_gate_passes_without_cargo() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_consensus_parity.py", "--source-only", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(
        proc.stdout.splitlines()[0] if proc.stdout.startswith("{") and "\n}" not in proc.stdout else proc.stdout
    )
    assert payload["ok"] is True
    assert payload["mode"] == "source-only"
    assert payload["consensus_cases"] >= 30


def test_v024_migration_status_reports_executable_lane() -> None:
    status = migration_status(ROOT)
    assert status["ok"] is True
    assert status["version"] in {
        "0.24.0",
        "0.25.0",
        "0.26.0",
        "0.31.0",
        "0.37.0",
        "0.37.1",
        "0.37.2",
        "0.37.3",
        "0.37.4",
    }
    consensus_lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-consensus-parity")
    assert consensus_lane["status"] == "executable-rust-consensus-parity-runner"
    assert "evidence_added_v024" in consensus_lane


def test_v024_makefile_has_release_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "v024-check" in makefile
    assert "rust-consensus-parity-check" in makefile
    assert "tools/run_rust_consensus_parity.py --allow-missing-cargo" in makefile
