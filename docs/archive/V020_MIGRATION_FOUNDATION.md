# NetCoin v0.20 Migration Foundation

v0.20 continues the professional architecture work by turning the empty future
lanes into structured migration foundations.

## Added

- Frozen starter parity vectors: `architecture/parity-vectors.json`
- Migration lane plan: `architecture/migration-plan.json`
- Migration status API: `GET /api/migration-status`
- Migration status helpers: `netcoin/migration_status.py`
- Rust parity-domain helpers in:
  - `core-rs/crates/consensus`
  - `core-rs/crates/node`
  - `core-rs/crates/wallet-core`
  - `core-rs/crates/markets-core`
- TypeScript API schema/client starter in `api/src/`
- Workspace checks:
  - `tools/check_migration_parity.py`
  - `tools/check_rust_workspace.py`
  - `tools/check_ts_workspace.py`

## Rule

No Rust or TypeScript replacement becomes live until it passes parity against the
Python reference implementation and the frozen vector set. The Python app remains
the current runnable reference.

## Final-version space

The repo now has explicit room for:

- Rust consensus/node/wallet/market-core
- TypeScript API/web app
- Python ops/reference/testing
- Desktop/mobile wallets later

This is not a rewrite yet. It is the safe migration foundation for the final
professional version.
