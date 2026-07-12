# M2 Fuzz Corpus Plan

M2 source gates require a fuzz plan; strict M2 requires saved high-iteration
evidence.

## Targets

- `consensus.py`: block validation, subsidy boundaries, transaction validity.
- `mempool.py` / chain mempool policy: RBF, CPFP, dust, duplicate inputs.
- transaction parser/serializer: JSON and binary-ish serialization boundaries.
- PSBT import/export/finalize.
- descriptor parsing.

## Strict evidence target

- 100M+ cumulative iterations across consensus, mempool, and tx parse targets.
- Saved seed corpus.
- Crash corpus triaged to zero unwaived critical/high issues.
- Report saved at `reports/m2_evidence/fuzz_100m_report.json`.
