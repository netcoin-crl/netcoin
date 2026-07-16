# NetCoin v0.22 Rust/TypeScript Parity Expansion

v0.22 expands the v0.21 parity bridge from a starter proof into a broader migration target for the future professional architecture.

## What changed

- Parity vectors moved to schema version 3.
- Consensus parity now covers transaction fee sanity, starter Merkle-root calculation, and deterministic subsidy reduction helpers.
- Wallet parity now covers fee-rate review/block thresholds, dust-change review, and recipient-reuse review decisions.
- Markets parity now covers maker/taker fee caps and minimum order notional checks.
- TypeScript contracts now include wallet preview, explorer transaction, market settlement, and parity-vector schemas.
- TypeScript client now exposes `parityVectors()` and `migrationReadiness()`.
- Rust starter crates now expose parity-facing helpers for the expanded vector set.
- New API routes expose frozen vectors and migration readiness: `/api/parity-vectors` and `/api/migration-readiness`.

## What did not change

The live runtime is still the Python reference app. Rust and TypeScript are still migration lanes and must continue proving parity before replacing live paths.

## Validation commands

```bash
python tools/run_parity_suite.py
python tools/check_rust_workspace.py
python tools/check_ts_workspace.py
python -m pytest -q tests/test_v022_rust_ts_parity_expansion.py
```

## Current status

- Executable parity suite: green
- Rust/TypeScript expansion symbols: present
- Final v1.0 readiness: still incomplete until full-suite, E2E, hostile P2P soak, native hardware signing, and external audit gates are complete.
