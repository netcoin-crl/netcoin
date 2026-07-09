from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import mempool_ordering_summary, mempool_policy_summary, run_parity_suite

ROOT = Path(__file__).resolve().parents[1]


def test_v025_expands_vectors_and_project_version() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 6
    assert report["total"] >= 78
    assert report["lanes"]["mempool"]["passed"] >= 12
    assert vectors["generated_by"] in {
        "netcoin-v0.25-rust-mempool-parity",
        "netcoin-v0.26-rust-wallet-core-parity",
        "netcoin-v0.31-rust-ts-full-parity-expansion",
    }
    assert vectors["mempool"]["vector_set"] == "mempool-policy-vectors-v1"
    assert vectors["mempool"]["valid_cases"] >= 3
    assert vectors["mempool"]["invalid_cases"] >= 9


def test_v025_python_reference_executes_mempool_vector_kinds() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["mempool"]["cases"]}
    assert mempool_policy_summary(cases["mempool-accept-standard-high-fee"])["code"] == "accepted"
    assert mempool_policy_summary(cases["mempool-reject-duplicate-txid"])["code"] == "duplicate"
    assert mempool_policy_summary(cases["mempool-reject-orphan-missing-prevout"])["code"] == "orphan"
    assert mempool_policy_summary(cases["mempool-reject-low-fee-rate"])["code"] == "low_fee_rate"
    assert mempool_policy_summary(cases["mempool-reject-dust-output"])["code"] == "dust"
    assert mempool_policy_summary(cases["mempool-reject-ancestor-limit"])["code"] == "too_many_ancestors"
    assert mempool_policy_summary(cases["mempool-reject-descendant-limit"])["code"] == "too_many_descendants"
    assert mempool_ordering_summary(cases["mempool-order-by-feerate-desc"])["ordered_txids"] == [
        "high",
        "tie-a",
        "tie-b",
        "low",
    ]


def test_v025_rust_mempool_files_symbols_and_fixture_exist() -> None:
    workspace = (ROOT / "core-rs/Cargo.toml").read_text(encoding="utf-8")
    lib = (ROOT / "core-rs/crates/mempool-core/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/mempool-core/src/bin/netcoin-mempool-parity.rs").read_text(encoding="utf-8")
    fixture = json.loads((ROOT / "core-rs/fixtures/parity-vectors.json").read_text(encoding="utf-8"))
    assert "crates/mempool-core" in workspace
    for symbol in [
        "MempoolPolicySummary",
        "mempool_fee_rate_sat_vb",
        "mempool_policy_summary",
        "mempool_ordering_summary",
        "run_mempool_case",
        "run_mempool_parity_vectors",
    ]:
        assert symbol in lib
    assert "run_mempool_parity_vectors" in binary
    assert "serde_json::to_string_pretty" in binary
    assert fixture["schema_version"] >= 6
    assert len(fixture["mempool"]["cases"]) >= 12


def test_v025_source_only_rust_mempool_comparison_gate_passes_without_cargo() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_mempool_parity.py", "--source-only", "--no-write"],
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
    assert payload["mempool_cases"] >= 12


def test_v025_migration_status_reports_mempool_lane() -> None:
    status = migration_status(ROOT)
    assert status["ok"] is True
    assert status["version"] >= "0.25.0"
    mempool_lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-mempool-parity")
    assert mempool_lane["status"] == "executable-rust-mempool-policy-parity-runner"
    assert mempool_lane["evidence"]["owner_exists"] is True
    assert "evidence_added_v025" in mempool_lane


def test_v025_makefile_has_release_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "v025-check" in makefile
    assert "rust-mempool-parity-check" in makefile
    assert "tools/run_rust_mempool_parity.py --allow-missing-cargo" in makefile
