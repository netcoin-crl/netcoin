from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import run_parity_suite, wallet_decision

ROOT = Path(__file__).resolve().parents[1]


def _json_from_stdout(stdout: str) -> dict:
    return json.loads(stdout)


def test_v026_expands_wallet_vectors_and_project_version() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 7
    assert report["total"] >= 90
    assert report["lanes"]["wallet"]["passed"] >= 21
    assert vectors["generated_by"] in {
        "netcoin-v0.26-rust-wallet-core-parity",
        "netcoin-v0.31-rust-ts-full-parity-expansion",
    }
    assert vectors["wallet"]["vector_set"] == "wallet-core-executable-vectors-v3"
    assert vectors["wallet"]["valid_cases"] >= 4
    assert vectors["wallet"]["review_cases"] >= 8
    assert vectors["wallet"]["blocked_cases"] >= 7


def test_v026_python_reference_executes_wallet_policy_boundaries() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["wallet"]["cases"]}
    assert wallet_decision(cases["preview-negative-amount"]) == "block"
    assert wallet_decision(cases["preview-negative-fee"]) == "block"
    assert wallet_decision(cases["preview-poison-warning"]) == "block"
    assert wallet_decision(cases["preview-borderline-fee-rate-allow"]) == "allow"
    assert wallet_decision(cases["preview-fee-rate-threshold-review"]) == "review"
    assert wallet_decision(cases["preview-fee-rate-threshold-block"]) == "block"
    assert wallet_decision(cases["preview-dust-threshold-allow"]) == "allow"
    assert wallet_decision(cases["preview-zero-dust-change-allow"]) == "allow"
    assert wallet_decision(cases["preview-hardware-signer-warning"]) == "review"
    assert wallet_decision(cases["preview-large-input-boundary-allow"]) == "allow"
    assert wallet_decision(cases["preview-large-input-over-limit-review"]) == "review"


def test_v026_rust_wallet_files_symbols_and_fixture_exist() -> None:
    lib = (ROOT / "core-rs/crates/wallet-core/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/wallet-core/src/bin/netcoin-wallet-parity.rs").read_text(encoding="utf-8")
    fixture = json.loads((ROOT / "core-rs/fixtures/parity-vectors.json").read_text(encoding="utf-8"))
    for symbol in [
        "WalletPolicyPreview",
        "policy_decision",
        "wallet_decision",
        "wallet_policy_summary",
        "run_wallet_case",
        "run_wallet_parity_vectors",
    ]:
        assert symbol in lib
    assert "run_wallet_parity_vectors" in binary
    assert "serde_json::to_string_pretty" in binary
    assert "process::exit" in binary
    assert fixture["schema_version"] >= 7
    assert fixture["wallet"]["vector_set"] == "wallet-core-executable-vectors-v3"
    assert len(fixture["wallet"]["cases"]) >= 21


def test_v026_source_only_rust_wallet_comparison_gate_passes_without_cargo() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_wallet_parity.py", "--source-only", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = _json_from_stdout(proc.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "source-only"
    assert payload["wallet_cases"] >= 21


def test_v026_migration_status_reports_wallet_lane() -> None:
    status = migration_status(ROOT)
    assert status["ok"] is True
    assert status["version"] in {"0.26.0", "0.31.0", "0.37.0", "0.37.1", "0.37.2", "0.37.3", "0.37.4", "0.38.0", "0.38.1", "0.38.2", "0.38.3"}
    wallet_lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-wallet-core")
    assert wallet_lane["status"] == "executable-rust-wallet-core-policy-parity-runner"
    assert wallet_lane["evidence"]["owner_exists"] is True
    assert wallet_lane["evidence"]["has_vector_set"] is True
    assert "evidence_added_v026" in wallet_lane


def test_v026_makefile_has_release_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "v026-check" in makefile
    assert "rust-wallet-parity-check" in makefile
    assert "tools/run_rust_wallet_parity.py --allow-missing-cargo" in makefile
