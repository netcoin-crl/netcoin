# Phase 1 Strict Proof Execution

NetCoin v0.39.1 extends Phase 1 from a proof-hardening manifest into an executable strict-proof playbook.

## Purpose

Phase 0 made the product coherent. Phase 1 proves the implementation. This document defines the local and CI bridge from sandbox/source-checked confidence to strict professional-candidate evidence.

## Rule

A professional-readiness claim is not allowed while any gate is `source_only`, `not_run`, `blocked`, or `fail`.

## Local strict proof

From the project root:

```bash
python tools/check_strict_proof_execution.py
python tools/print_strict_proof_plan.py --profile macos
python tools/run_release_readiness.py --strict --timeout 300
```

The strict scorecard must write:

```text
reports/release_readiness_scorecard.json
```

## Required strict lanes

1. Python reference tests and parity.
2. Rust workspace build and tests.
3. All Rust executable parity lanes.
4. TypeScript API build, contract, and parity.
5. Browser E2E product matrix.
6. Accessibility matrix.
7. Security and release evidence.
8. Phase 0 product guardrails.

## CI workflow

The workflow `.github/workflows/proof-hardening.yml` separates Python, Rust, TypeScript, browser/accessibility, and release-readiness jobs so blockers are clear.

## Handoff to the next Phase 1 release

The next hardening pass should run this workflow locally/CI and fix the first strict failing lane instead of adding new product features.
