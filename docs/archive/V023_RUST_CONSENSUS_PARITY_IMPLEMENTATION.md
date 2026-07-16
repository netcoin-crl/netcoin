# NetCoin v0.23 Rust Consensus Parity Implementation

v0.23 moves the Rust migration lane from starter helper coverage toward real consensus-parity evidence while keeping Python as the live reference runtime.

## What changed

- Expanded `architecture/parity-vectors.json` to schema version 4.
- Increased the executable parity suite from 50 checks to 60 checks.
- Added transaction-shape vectors for standard spends, coinbase transactions, and malformed empty-input transactions.
- Added block-header hash vectors using the same canonical JSON and double-SHA256 convention as the Python reference helper.
- Added basic UTXO spend validation vectors covering valid spends, overspends, duplicate inputs, immature coinbase spends, and missing prevouts.
- Copied the frozen vector set into `core-rs/fixtures/parity-vectors.json` for Rust-side fixture tests.
- Expanded `core-rs/crates/consensus/src/lib.rs` with Rust implementations for:
  - `tx_parse_summary`
  - `block_header_summary`
  - `basic_utxo_ok`
  - `headers_link_value`
  - `checkpoint_value_ok`
- Reworked the Rust consensus fixture test so every consensus vector kind must be handled explicitly.
- Fixed the TypeScript parity bridge export so `tools/check_ts_workspace.py` recognizes `ParityStatusSchema` from `api/src/parity.ts`.

## Validation status

Validated in this environment:

```bash
python -m compileall -q netcoin tools
python tools/run_parity_suite.py --no-write
python tools/check_migration_parity.py
python tools/check_rust_workspace.py
python tools/check_ts_workspace.py
make test-fast
make v022-check
```

`cargo test` was not run in this sandbox because Cargo/Rust is not installed here. The Rust workspace structural checker and frozen Rust fixture test source were updated, but a machine with Rust installed should still run:

```bash
cd core-rs && cargo test --workspace
```

## Still not live Rust consensus

This release still does **not** replace Python consensus. Rust remains a parity lane until the final gates pass: full Python test suite, Rust vector parity, hostile P2P soak, OpenAPI parity, browser E2E, release provenance, hardware/offline signing checks, and external security audit.
