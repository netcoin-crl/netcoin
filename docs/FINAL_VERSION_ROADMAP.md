# NetCoin Final Version Roadmap

## v0.19 — Architecture space

Create the professional Rust/TypeScript/Python layout while keeping Python as the runnable reference app.

## v0.20 — Vector freeze

Freeze consensus, wallet, script, market, indexer, and API vectors. No Rust migration should replace live code before vector parity exists.

## v0.30 — Rust core MVP

Port serialization, hashing, tx/block validation, UTXO checks, and mempool policy into `core-rs`.

## v0.40 — Rust node/indexer MVP

Port P2P sync, peer scoring, chainstate, and indexer ingestion into Rust services.

## v0.50 — TypeScript app migration

Replace copied static site shells with a unified typed app while preserving current pages until E2E parity passes.

## v0.70 — Desktop/mobile wallet

Ship Tauri desktop wallet and mobile wallet using shared wallet-core vectors.

## v0.90 — Audit candidate

Run full suite, browser E2E, hostile P2P soak, market stress, custody drills, release verification, and third-party review prep.

## v1.0 — Production candidate

Only after external audit, public hostile testnet evidence, and signed release/provenance gates are complete.

## v0.22 Rust/TypeScript parity expansion

v0.22 expands frozen parity vectors and adds wider Rust/TypeScript parity symbols. This is a migration milestone, not a live runtime replacement.

Completed next milestone: v0.24 adds a real Rust consensus parity binary and a Python comparison wrapper; the next recommended milestone is v0.25 mempool policy parity.


## v0.23 Rust consensus parity implementation

v0.23 expands the Rust consensus lane from helper parity into frozen vectors for transaction-shape summaries, block-header hashing, and basic UTXO spend validation. Python remains the live reference runtime; Rust still cannot replace consensus until the full final gates pass.

Validation target:

```bash
make v023-check
cd core-rs && cargo test --workspace
```

## v0.24 Rust executable consensus parity

v0.24 adds the first Rust consensus executable parity runner. The Rust `netcoin-consensus-parity` binary reads the canonical JSON vectors and emits per-case JSON results. The Python wrapper `tools/run_rust_consensus_parity.py` runs Cargo when available and compares Rust outputs against Python reference outputs. This is the next bridge toward Rust-owned consensus, but Python remains the live reference until final gates pass.
