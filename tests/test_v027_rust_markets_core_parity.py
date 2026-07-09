from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import (
    collateral_ok,
    lifecycle_allows_order,
    order_crosses,
    portfolio_conserves,
    price_tick_ok,
    run_parity_suite,
    settlement_state_ok,
)

ROOT = Path(__file__).resolve().parents[1]


def _json_from_stdout(stdout: str) -> dict:
    return json.loads(stdout)


def test_v027_markets_parity_suite_is_green() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 8
    assert report["total"] >= 103
    assert report["lanes"]["markets"]["passed"] >= 24
    assert vectors["markets"]["vector_set"] == "markets-core-executable-vectors-v4"


def test_v027_python_reference_executes_market_boundaries() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["markets"]["cases"]}
    assert price_tick_ok(cases["price-tick-valid-50bps"]) is True
    assert price_tick_ok(cases["price-tick-reject-off-grid"]) is False
    assert collateral_ok(cases["collateral-sufficient"]) is True
    assert collateral_ok(cases["collateral-insufficient"]) is False
    assert order_crosses(cases["buy-crosses-best-ask"]) is True
    assert order_crosses(cases["sell-does-not-cross-best-bid"]) is False
    assert lifecycle_allows_order(cases["open-market-allows-orders"]) is True
    assert lifecycle_allows_order(cases["resolved-market-blocks-orders"]) is False
    assert settlement_state_ok(cases["resolved-state-with-outcome"]) is True
    assert portfolio_conserves(cases["portfolio-equity-conserves"]) is True


def test_v027_rust_markets_files_symbols_and_source_gate() -> None:
    lib = (ROOT / "core-rs/crates/markets-core/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/markets-core/src/bin/netcoin-markets-parity.rs").read_text(encoding="utf-8")
    for symbol in [
        "run_market_case",
        "run_markets_parity_vectors",
        "price_tick_ok",
        "collateral_ok",
        "order_crosses",
        "portfolio_conserves",
    ]:
        assert symbol in lib
    assert "run_markets_parity_vectors" in binary
    assert "serde_json::to_string_pretty" in binary
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_markets_parity.py", "--source-only", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = _json_from_stdout(proc.stdout)
    assert payload["ok"] is True
    assert payload["markets_cases"] >= 24


def test_v027_migration_status_reports_markets_lane() -> None:
    status = migration_status(ROOT)
    lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-markets-core")
    assert lane["status"] == "executable-rust-markets-core-parity-runner"
    assert lane["evidence"]["owner_exists"] is True
    assert lane["evidence"]["has_vector_set"] is True
