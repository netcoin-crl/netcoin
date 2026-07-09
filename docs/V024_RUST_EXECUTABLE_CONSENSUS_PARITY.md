# NetCoin v0.24 Rust Executable Consensus Parity

v0.24 turns the Rust consensus migration lane from source-level parity coverage into an executable comparison boundary.
Python remains the live/reference runtime, but the Rust consensus crate now includes a binary that can read the same frozen parity vectors and emit machine-readable JSON results.

## What changed

- Added Rust binary:

```text
core-rs/crates/consensus/src/bin/netcoin-consensus-parity.rs
```

- Added Rust library execution helpers:

```text
run_consensus_case
run_consensus_parity_vectors
```

- Added Python comparison wrapper:

```text
tools/run_rust_consensus_parity.py
```

- Expanded the frozen vector set to schema version 5 and consensus vector set `consensus-executable-vectors-v4`.
- Synchronized the canonical vector copies:

```text
architecture/parity-vectors.json
core-rs/fixtures/parity-vectors.json
api/fixtures/parity-vectors.json
```

- Added `make v024-check`.
- Added regression coverage in `tests/test_v024_rust_executable_consensus_parity.py`.

## Intended local Rust command

Run this on a machine with Rust/Cargo installed:

```bash
cd core-rs
cargo run -q -p netcoin-consensus --bin netcoin-consensus-parity -- ../architecture/parity-vectors.json
```

The binary prints JSON with `ok`, `total`, `passed`, `failed`, and per-case results.

## Python comparison command

From the project root:

```bash
python tools/run_rust_consensus_parity.py
```

That command runs Cargo when available and compares every Rust consensus result with the Python reference parity implementation.

In constrained sandboxes where Cargo is unavailable, this source-only check can be used without claiming a live Rust execution:

```bash
python tools/run_rust_consensus_parity.py --allow-missing-cargo
```

## Important boundary

This still does **not** replace the Python live consensus path. Rust can only be promoted after the full final gates pass, including hostile P2P soak, chainstate parity, full suite green, and audit evidence.
