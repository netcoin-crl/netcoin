# NetCoin v0.27 Rust Markets-Core Executable Parity

NetCoin v0.27 expands the Rust migration boundary to prediction-market invariants. The live market app remains Python/reference; Rust markets-core must match frozen vectors before any promotion.

Added coverage:

- quote validity
- YES/NO probability sum
- settlement conservation
- fee-cap checks
- order notional checks
- price tick validation
- collateral sufficiency
- crossing behavior
- market lifecycle restrictions
- settlement-state rules
- portfolio/equity conservation

Key files:

- `core-rs/crates/markets-core/src/lib.rs`
- `core-rs/crates/markets-core/src/bin/netcoin-markets-parity.rs`
- `tools/run_rust_markets_parity.py`
- `tests/test_v027_rust_markets_core_parity.py`

Gate:

```bash
make v027-check
```
