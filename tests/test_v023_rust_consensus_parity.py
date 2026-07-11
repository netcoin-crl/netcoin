from __future__ import annotations

import json
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import basic_utxo_ok, block_header_summary, run_parity_suite, tx_parse_summary

ROOT = Path(__file__).resolve().parents[1]


def test_v023_expands_consensus_parity_vectors() -> None:
    report = run_parity_suite(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 4
    assert report["total"] >= 60
    assert report["lanes"]["consensus"]["passed"] >= 24
    vectors = parity_vectors(ROOT)
    assert vectors["generated_by"] in {
        "netcoin-v0.23-rust-consensus-parity-implementation",
        "netcoin-v0.24-rust-executable-consensus-parity",
        "netcoin-v0.25-rust-mempool-parity",
        "netcoin-v0.26-rust-wallet-core-parity",
        "netcoin-v0.31-rust-ts-full-parity-expansion",
    }
    assert vectors["consensus"]["vector_set"] in {"consensus-executable-vectors-v3", "consensus-executable-vectors-v4"}


def test_v023_python_reference_executes_new_vector_kinds() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["consensus"]["cases"]}
    assert tx_parse_summary(cases["tx-parse-standard-summary"]["tx"])["total_output_sats"] == 149000
    assert tx_parse_summary(cases["tx-parse-coinbase-summary"]["tx"])["coinbase"] is True
    assert tx_parse_summary(cases["tx-parse-empty-inputs"]["tx"]) == {"valid": False}
    assert (
        block_header_summary(cases["block-header-hash-v1"]["header"])
        == cases["block-header-hash-v1"]["expected_summary"]
    )
    assert block_header_summary(cases["block-header-invalid-prev-hash"]["header"]) == {"valid": False}
    assert basic_utxo_ok(cases["basic-utxo-valid-spend"]) is True
    assert basic_utxo_ok(cases["basic-utxo-overspend"]) is False
    assert basic_utxo_ok(cases["basic-utxo-duplicate-input"]) is False
    assert basic_utxo_ok(cases["basic-utxo-immature-coinbase"]) is False


def test_v023_rust_consensus_symbols_and_fixture_are_updated() -> None:
    consensus = (ROOT / "core-rs/crates/consensus/src/lib.rs").read_text(encoding="utf-8")
    test_source = (ROOT / "core-rs/crates/consensus/tests/parity_vectors.rs").read_text(encoding="utf-8")
    for symbol in [
        "tx_parse_summary",
        "block_header_summary",
        "basic_utxo_ok",
        "headers_link_value",
        "checkpoint_value_ok",
    ]:
        assert symbol in consensus
        assert symbol in test_source
    fixture = json.loads((ROOT / "core-rs/fixtures/parity-vectors.json").read_text(encoding="utf-8"))
    assert fixture["schema_version"] >= 4
    assert len(fixture["consensus"]["cases"]) >= 24


def test_v023_migration_status_reports_new_version() -> None:
    status = migration_status(ROOT)
    assert status["ok"] is True
    assert status["version"] in {
        "0.23.0",
        "0.24.0",
        "0.25.0",
        "0.26.0",
        "0.31.0",
        "0.37.0",
        "0.37.1",
        "0.37.2",
        "0.37.3",
        "0.37.4",
        "0.38.0",
        "0.38.1",
        "0.38.2",
        "0.38.3",
    }
    consensus_lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-consensus-parity")
    assert consensus_lane["status"] in {
        "expanded-consensus-vector-implementation",
        "executable-rust-consensus-parity-runner",
    }
