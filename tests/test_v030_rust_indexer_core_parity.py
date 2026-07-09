from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import (
    indexer_address_summary,
    indexer_market_event_summary,
    indexer_reorg_summary,
    indexer_snapshot_hash,
    run_parity_suite,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v030_indexer_parity_suite_is_green() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 11
    assert report["lanes"]["indexer"]["passed"] >= 10
    assert vectors["indexer"]["vector_set"] == "indexer-core-snapshot-vectors-v1"


def test_v030_python_reference_executes_indexer_vectors() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["indexer"]["cases"]}
    assert indexer_address_summary(cases["indexer-address-simple-balance"])["balance_sats"] == 85000
    assert indexer_reorg_summary(cases["indexer-reorg-three-rollback-two-apply"])["rollback_blocks"] == 3
    assert indexer_market_event_summary(cases["indexer-market-event-rollup"])["trade_volume_sats"] == 35000
    assert len(indexer_snapshot_hash(cases["indexer-snapshot-hash-address"])) == 64


def test_v030_rust_indexer_files_symbols_and_source_gate() -> None:
    lib = (ROOT / "core-rs/crates/indexer-core/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/indexer-core/src/bin/netcoin-indexer-parity.rs").read_text(encoding="utf-8")
    for symbol in [
        "indexer_address_summary",
        "indexer_reorg_summary",
        "indexer_market_event_summary",
        "indexer_snapshot_hash",
        "run_indexer_case",
        "run_indexer_parity_vectors",
    ]:
        assert symbol in lib
    assert "run_indexer_parity_vectors" in binary
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_indexer_parity.py", "--source-only", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["indexer_cases"] >= 10


def test_v030_migration_status_reports_indexer_lane() -> None:
    status = migration_status(ROOT)
    lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-indexer-core")
    assert lane["status"] == "executable-rust-indexer-core-parity-runner"
    assert lane["evidence"]["owner_exists"] is True
    assert lane["evidence"]["has_vector_set"] is True
