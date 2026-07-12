# Phase 0 — Clean Baseline and CI Proof

## Goal

Establish a trusted starting point that every future task builds from.

## Required evidence

- Local full test suite passes.
- Coverage gate passes.
- Black check passes.
- Site UI polish passes.
- Rust workspace passes.
- TypeScript API CI passes.
- Browser E2E passes.
- Accessibility strict passes.
- GitHub CI push lanes pass.

## Verification commands

```bash
git rev-parse HEAD
git status --short
.venv/bin/python -m black --check netcoin tests tools
.venv/bin/python -m pytest tests/ -q
.venv/bin/python tools/coverage_gate.py --minimum 55 --group-minimum 35 --packages consensus:40,wallet:35,mempool:35,markets:35,storage:35,api_auth:50
cargo test --workspace --manifest-path core-rs/Cargo.toml
cd api && npm run parity && npm run ci:api
python3 tools/run_browser_e2e_matrix.py --run-playwright
python3 tools/run_accessibility_matrix.py --strict
gh run list --branch main --event push --limit 3
```

## Exit criteria

- All local checks green.
- GitHub CI green.
- No uncommitted files except intended local reports.
