# NetCoin v0.26 Rust Wallet-Core Executable Parity

NetCoin v0.26 upgrades the wallet migration lane from starter Rust policy helpers into an executable Rust wallet-core parity boundary. The live wallet remains Python/reference; Rust must match frozen wallet policy/risk vectors before any promotion.

## What changed

- Added `core-rs/crates/wallet-core/src/bin/netcoin-wallet-parity.rs` so Rust can execute frozen wallet vectors and emit JSON results.
- Expanded `core-rs/crates/wallet-core/src/lib.rs` with fixture-driven wallet policy helpers:
  - `wallet_decision`
  - `wallet_policy_summary`
  - `run_wallet_case`
  - `run_wallet_parity_vectors`
- Added `tools/run_rust_wallet_parity.py` to compare Rust wallet outputs with the Python reference outputs when Cargo is available.
- Expanded the wallet vector set to `wallet-core-executable-vectors-v3`.
- Expanded the parity suite from 78 to 90 executable checks.
- Added `make v026-check`.

## Covered wallet policy vectors

The v0.26 wallet-core lane covers:

- safe send allow decision
- high fee review decision
- frozen coin block decision
- negative balance block decision
- many-input review decision
- fee-rate review and block thresholds
- negative amount and negative fee blocks
- address-poison warning block
- dust-change review and dust-threshold allow boundaries
- zero-change/send-max allow boundary
- recipient reuse review
- hardware signer required review
- offline signing recommended review
- large-input boundary allow/review split

## Important boundary

This is still a migration boundary only. Rust wallet-core does not replace the Python wallet. Promotion requires more vector coverage for coin selection, signing, address derivation, PSBT/offline signing, hardware-signing adapters, browser-vault flows, and full Rust/Cargo CI execution.

## Validation

Sandbox-safe validation:

```bash
python -m compileall -q netcoin tools
python tools/run_parity_suite.py --no-write
python tools/run_rust_consensus_parity.py --source-only --no-write
python tools/run_rust_mempool_parity.py --source-only --no-write
python tools/run_rust_wallet_parity.py --source-only --no-write
python tools/check_rust_workspace.py
python tools/check_ts_workspace.py
python tools/check_migration_parity.py
make v026-check
```

Rust-enabled validation:

```bash
cd core-rs
cargo test --workspace
cargo run -q -p netcoin-consensus --bin netcoin-consensus-parity -- ../architecture/parity-vectors.json
cargo run -q -p netcoin-mempool-core --bin netcoin-mempool-parity -- ../architecture/parity-vectors.json
cargo run -q -p netcoin-wallet-core --bin netcoin-wallet-parity -- ../architecture/parity-vectors.json
```
