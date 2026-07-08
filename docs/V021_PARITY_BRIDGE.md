# NetCoin v0.21 Parity Bridge

v0.21 turns the architecture migration space into an executable bridge between the current Python reference app and the future Rust/TypeScript system.

## Added

- Expanded executable parity vectors in `architecture/parity-vectors.json`.
- Python reference runner: `netcoin/parity_suite.py`.
- CLI report tool: `tools/run_parity_suite.py`.
- API route: `GET /api/parity-status`.
- TypeScript parity schema: `api/src/parity.ts`.
- Rust parity fixtures under `core-rs/fixtures/`.
- TypeScript parity fixtures under `api/fixtures/`.
- Additional migration lanes for P2P sync, indexer core, and parity reporting.
- Compatibility fix for header-sync chains that validate headers in-place and return `None`.

## Rule

Rust or TypeScript code still does **not** replace live Python behavior. A lane can only be promoted after it matches the executable parity vectors, passes product/API checks, and has rollback documentation.
