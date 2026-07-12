# M2 Trust Hardening

M2's exit gate is: an outside security-minded user can review NetCoin and say,
"I would use this to hold my own testnet coins."

This repository can be made **M2 source-complete** offline. It cannot be made
**M2 operationally complete** without external evidence: physical Ledger/Trezor
transcripts, real release-signing keys, reproducible builds on a second machine,
high-iteration fuzz results, and audit-firm review.

## Deliverables in this package

1. Hardware-wallet signing contract for Ledger/Trezor-style flows.
2. PSBT create/export/sign/import/finalize coverage.
3. RBF and CPFP fee-bump helpers.
4. xpub/watch-only descriptor coverage.
5. Reproducible-build recipe and verifier.
6. Signed-release/SBOM/SLSA-style provenance hooks.
7. Fuzz corpus plan for consensus, mempool, and tx parsing.
8. Public bug bounty scope and audit scoping package.
9. CVE-focused threat model review.

## Honest claim language

Allowed after source gates pass:

> M2 is source-complete and ready for strict evidence collection.

Not allowed until strict evidence exists:

> M2 is complete.
> Hardware wallet support is production-tested.
> Releases are reproducible across independent builders.
> NetCoin has passed external audit.

## Local source gate

```bash
python3 tools/check_m2_readiness.py --out reports/m2_readiness_source_report.json
python3 tools/run_m2_release_candidate.py --profile source --out reports/m2_release_candidate_report.json
```

## Strict evidence gate

```bash
python3 tools/run_m2_release_candidate.py --profile strict --timeout 300 --out reports/m2_release_candidate_report.json
```

Strict mode intentionally fails if external evidence files are missing.
