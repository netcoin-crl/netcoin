# NetCoin v0.30 Rust Indexer-Core Executable Parity

NetCoin v0.30 adds a Rust indexer-core migration lane for explorer/indexer snapshots. The Python indexer remains the reference implementation.

Added coverage:

- address received/sent/balance summaries
- empty address history
- negative net address history
- reorg rollback/apply counts
- market-event rollups
- deterministic indexer snapshot hashes

Key files:

- `core-rs/crates/indexer-core/src/lib.rs`
- `core-rs/crates/indexer-core/src/bin/netcoin-indexer-parity.rs`
- `tools/run_rust_indexer_parity.py`
- `tests/test_v030_rust_indexer_core_parity.py`

Gate:

```bash
make v030-check
```
