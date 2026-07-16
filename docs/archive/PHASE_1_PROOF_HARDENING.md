# NetCoin v0.39.0 Phase 1 Proof Hardening

Phase 0 made NetCoin coherent: product identity, design system, simplification rules, trust language, and no-dead-end workflow standards are now defined.

Phase 1 starts the proof-hardening arc. It does not add broad new features. It turns existing claims into executable evidence.

## Purpose

Phase 1 answers one question:

> Can this version be trusted across Python reference, Rust core, TypeScript API, browser UI, release/security gates, and Phase 0 product guardrails?

## New artifacts

- `architecture/proof-hardening.json` - canonical proof manifest.
- `netcoin/proof_hardening.py` - manifest and scorecard helpers.
- `tools/check_proof_hardening.py` - validates the proof manifest.
- `tools/run_all_rust_parity.py` - runs all Rust parity wrappers in one lane.
- `tools/run_accessibility_matrix.py` - accessibility source/strict gate scaffold.
- `tools/run_release_readiness.py` - writes `reports/release_readiness_scorecard.json`.
- `tests/test_v039_phase1_proof_hardening.py` - regression tests.

## Modes

### Sandbox mode

Sandbox mode is for restricted environments. It runs deterministic source checks and marks external proofs as source-only when Cargo, npm installs, or browsers are unavailable.

```bash
python tools/run_release_readiness.py
```

This can support a source-checked testnet claim, not professional/mainnet readiness.

### Strict mode

Strict mode is the real professional gate.

```bash
python tools/run_release_readiness.py --strict
```

Strict mode must not contain `source_only`, `blocked`, `not_run`, or `fail` statuses before NetCoin can claim professional-candidate readiness.

## Local strict proof commands

Run these on a fully provisioned local machine or CI runner:

```bash
python tools/run_release_readiness.py --strict
cd core-rs && cargo test --workspace
cd ../api && npm ci && npm run ci:api
cd .. && python tools/run_all_rust_parity.py --strict
python tools/run_browser_e2e_matrix.py --run-playwright
python tools/run_accessibility_matrix.py --strict
```

## Phase 1 exit criteria

Phase 1 is complete only when:

1. Full Python suite is stable or all failures have tracked blockers.
2. Cargo workspace tests pass.
3. All Rust parity binaries execute without `--allow-missing-cargo`.
4. `npm ci && npm run ci:api` passes from a clean API directory.
5. Browser E2E runs for wallet, explorer, markets, faucet, operator, exchange, and release verify.
6. Accessibility matrix is tracked and strict execution is green or explicitly blocked.
7. The release readiness scorecard is generated for every release.

## Non-goals

- No new product surface.
- No new market, custody, wallet, or social feature unless it directly supports a proof gate.
- No production/mainnet claim from sandbox-only evidence.
