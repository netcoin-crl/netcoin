# NetCoin v0.29 Rust P2P/Header-Sync Executable Parity

NetCoin v0.29 moves P2P/header-sync migration evidence into Rust node code. This is not the live network stack; it is a parity boundary for peer selection, header linking, checkpoint checks, protocol compatibility, and ban-score policy.

Added coverage:

- best-peer selection by chainwork/height/score
- banned peer exclusion
- linked header acceptance
- unlinked header rejection
- checkpoint mismatch rejection
- protocol mismatch rejection
- ban score thresholds

Key files:

- `core-rs/crates/node/src/lib.rs`
- `core-rs/crates/node/src/bin/netcoin-p2p-parity.rs`
- `tools/run_rust_p2p_parity.py`
- `tests/test_v029_rust_p2p_sync_parity.py`

Gate:

```bash
make v029-check
```
