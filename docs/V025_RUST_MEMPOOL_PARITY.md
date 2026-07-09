# NetCoin v0.25 Rust Mempool Parity

NetCoin v0.25 adds the first dedicated Rust mempool migration lane while keeping the Python implementation as the live reference runtime.

## What changed

- Added `core-rs/crates/mempool-core/` as a Rust migration crate for mempool policy parity.
- Added `core-rs/crates/mempool-core/src/bin/netcoin-mempool-parity.rs` so Rust can execute frozen mempool vectors and emit JSON results.
- Added `tools/run_rust_mempool_parity.py` to compare Rust mempool outputs with Python reference outputs when Cargo is available.
- Added a new `mempool` lane to `architecture/parity-vectors.json` and synchronized it to:
  - `api/fixtures/parity-vectors.json`
  - `core-rs/fixtures/parity-vectors.json`
- Expanded the parity suite from 66 to 78 executable checks.
- Added `make v025-check`.

## Covered mempool policy vectors

The first mempool parity lane covers:

- standard high-fee transaction acceptance
- duplicate txid rejection
- orphan / missing prevout rejection
- low fee-rate rejection
- dust output rejection
- nonfinal locktime rejection
- ancestor package limit rejection
- descendant package limit rejection
- max transaction vsize rejection
- insufficient RBF bump rejection
- sufficient RBF bump acceptance
- fee-rate ordering for block-template priority

## Important boundary

The Rust crate is a migration boundary only. It does not replace the live Python mempool yet. Promotion requires more vectors, hostile network testing, package relay cases, expiry/eviction parity, and Rust/Cargo checks in CI.

## Validation

Sandbox-safe validation:

```bash
python -m compileall -q netcoin tools
python tools/run_parity_suite.py --no-write
python tools/run_rust_consensus_parity.py --source-only --no-write
python tools/run_rust_mempool_parity.py --source-only --no-write
python tools/check_rust_workspace.py
python tools/check_ts_workspace.py
python tools/check_migration_parity.py
make v025-check
```

Rust-enabled validation:

```bash
cd core-rs
cargo test --workspace
cargo run -q -p netcoin-consensus --bin netcoin-consensus-parity -- ../architecture/parity-vectors.json
cargo run -q -p netcoin-mempool-core --bin netcoin-mempool-parity -- ../architecture/parity-vectors.json
```
