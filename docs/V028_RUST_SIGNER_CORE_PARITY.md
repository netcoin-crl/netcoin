# NetCoin v0.28 Rust Signer-Core Executable Parity

NetCoin v0.28 adds a Rust signer-core migration lane for offline-signing and hardware-policy safety. The Python signer/reference layer remains live.

Added coverage:

- deterministic signing payload digest vectors
- multisig threshold policy
- hardware large-send review
- offline signing review
- unknown sighash rejection
- negative amount rejection
- offline envelope validity and digesting

Key files:

- `core-rs/crates/signer-core/src/lib.rs`
- `core-rs/crates/signer-core/src/bin/netcoin-signer-parity.rs`
- `tools/run_rust_signer_parity.py`
- `tests/test_v028_rust_signer_core_parity.py`

Gate:

```bash
make v028-check
```
