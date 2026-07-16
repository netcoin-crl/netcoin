# Phase 1 Proof Triage and CI Alignment

NetCoin v0.39.4 adds the final practical layer on top of the Phase 1 proof runner: triage.

Phase 1 already has source checks, strict proof definitions, evidence collection, and a local proof runner. The missing piece was a clear answer after a proof run fails:

- What failed?
- Is it a missing tool, command failure, source-only caveat, missing artifact, timeout, or skipped gate?
- Who owns it?
- Which exact command should be run next?
- Does CI cover the same proof path?

The proof triage layer answers those questions.

## New files

- `architecture/proof-triage.json`
- `netcoin/proof_triage.py`
- `tools/check_proof_triage.py`
- `tools/run_proof_triage.py`
- `tools/run_v0394_check.py`
- `tests/test_v0394_phase1_proof_triage.py`

## Triage classes

The report classifies issues into:

- `missing-tool`
- `command-failure`
- `source-only-evidence`
- `missing-artifact`
- `timeout`
- `not-run`

Each item has a severity, owner, next command, and remediation text.

## CI alignment

The triage manifest checks that `.github/workflows/proof-hardening.yml` exists and names the required proof jobs. This does not replace CI execution. It makes sure local proof language and CI proof language remain aligned.

## Commands

```bash
python tools/check_proof_triage.py
python tools/run_local_proof.py --profile sandbox --timeout 120
python tools/collect_proof_evidence.py --mode sandbox
python tools/run_proof_triage.py
make v0394-check
```

For strict local proof:

```bash
python tools/run_local_proof.py --profile strict --timeout 300
python tools/collect_proof_evidence.py --mode strict
python tools/run_proof_triage.py
```

## Claim rule

A triage report with source-only items is useful for testnet/source-checked releases. It is not professional readiness proof. Professional readiness requires strict local or CI execution with no fail, blocked, source-only, not-run, or missing-artifact items.
