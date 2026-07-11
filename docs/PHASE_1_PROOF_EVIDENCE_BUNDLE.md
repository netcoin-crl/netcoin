# Phase 1 Proof Evidence Bundle

NetCoin v0.39.2 adds the proof-evidence bundle layer for Phase 1.

The goal is to stop release proof from being scattered across terminal logs.
A release candidate should produce one bundle that tells reviewers:

- which gates ran,
- which artifacts exist,
- which artifacts are source-only,
- which artifacts are missing,
- which hashes identify the artifacts,
- and what to do next for every blocker.

## Commands

Sandbox/source mode:

```bash
python tools/check_proof_evidence.py
python tools/collect_proof_evidence.py --refresh
```

Strict local mode, after installing Rust, npm dependencies, and Playwright:

```bash
python tools/run_release_readiness.py --strict --timeout 300
python tools/collect_proof_evidence.py --mode strict
```

## Output

Default bundle path:

```text
reports/proof_evidence_bundle.json
```

The bundle includes SHA-256 hashes for discovered artifacts and remediation for
missing or source-only gates. Sandbox bundles may still be useful, but they must
not be marketed as professional/mainnet proof.

## Claim levels

- `source-checked-testnet`: structure and source checks passed, but some strict gates are not executed.
- `strict-local-candidate`: local machine strict proof passed.
- `ci-proven-candidate`: CI ran the strict proof suite.
- `audit-candidate`: strict proof plus audit-prep evidence is complete.
