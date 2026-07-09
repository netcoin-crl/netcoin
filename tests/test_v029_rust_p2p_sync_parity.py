from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import p2p_ban_score_summary, p2p_header_sync_summary, p2p_peer_summary, run_parity_suite

ROOT = Path(__file__).resolve().parents[1]


def test_v029_p2p_parity_suite_is_green() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 10
    assert report["lanes"]["p2p"]["passed"] >= 10
    assert vectors["p2p"]["vector_set"] == "p2p-header-sync-vectors-v1"


def test_v029_python_reference_executes_p2p_vectors() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["p2p"]["cases"]}
    assert p2p_peer_summary(cases["p2p-best-peer-highest-chainwork"])["best_peer"] == "b"
    assert p2p_header_sync_summary(cases["p2p-header-sync-accept-linked"])["accepted"] is True
    assert p2p_header_sync_summary(cases["p2p-header-sync-reject-unlinked"])["accepted"] is False
    assert p2p_ban_score_summary(cases["p2p-ban-score-at-threshold"])["banned"] is True


def test_v029_rust_p2p_files_symbols_and_source_gate() -> None:
    lib = (ROOT / "core-rs/crates/node/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/node/src/bin/netcoin-p2p-parity.rs").read_text(encoding="utf-8")
    for symbol in [
        "p2p_best_peer_summary",
        "p2p_header_sync_summary",
        "p2p_ban_score_summary",
        "run_p2p_case",
        "run_p2p_parity_vectors",
    ]:
        assert symbol in lib
    assert "run_p2p_parity_vectors" in binary
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_p2p_parity.py", "--source-only", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["p2p_cases"] >= 10


def test_v029_migration_status_reports_p2p_lane() -> None:
    status = migration_status(ROOT)
    lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-p2p-sync")
    assert lane["status"] == "executable-rust-p2p-header-sync-parity-runner"
    assert lane["evidence"]["owner_exists"] is True
    assert lane["evidence"]["has_vector_set"] is True
