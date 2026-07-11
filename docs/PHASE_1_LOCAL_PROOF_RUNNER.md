# Phase 1 Local Proof Runner (v0.39.3)

NetCoin v0.39.3 adds a local proof runner for Phase 1. Earlier Phase 1
layers defined proof gates, strict execution expectations, and evidence bundle
collection. This layer makes those gates easier to run and debug locally by
capturing every gate as structured JSON plus a full log file.

## Purpose

The local proof runner does not add product features. It improves release proof
quality by making local and CI proof runs reproducible, inspectable, and ready
for evidence collection.

## Main commands

Sandbox/source-checked run:

```bash
python tools/run_local_proof.py --profile sandbox
```

Strict local run:

```bash
python tools/run_local_proof.py --profile strict --timeout 300
```

Validate the runner manifest:

```bash
python tools/check_local_proof_runner.py
```

Collect evidence after a run:

```bash
python tools/collect_proof_evidence.py --mode strict
```

## Outputs

The runner writes:

```text
reports/local_proof_run_report.json
reports/proof_runs/<run_id>/<gate_id>.json
reports/proof_runs/<run_id>/<gate_id>.log
```

The summary report includes gate status counts, blockers, claim level, run id,
and the path to the per-gate artifacts.

## Status meanings

- `pass`: the gate command succeeded.
- `source_only`: sandbox profile checked source structure but did not execute the external proof.
- `blocked`: strict mode could not run because a required external tool was missing.
- `fail`: the command executed and returned failure or timed out.
- `not_run`: a gate did not have commands for the selected profile.

## Release claim rule

Sandbox mode can only support a `source-checked-testnet` claim. Professional or
mainnet-candidate claims require strict mode with no `fail`, `blocked`,
`not_run`, or `source_only` gates.
