# M4 — Mainnet Readiness Plan

## Goal

Reach a point where mainnet could be launched with a straight face.

## Non-negotiable blockers

M4 cannot close without:

- external audit completion,
- protocol spec freeze,
- genesis distribution approval,
- legal posture/counsel review,
- entity/foundation decision,
- performance benchmark report,
- cold-storage ceremony.

## Workstreams

### M4.1 Protocol specification

- Freeze block format.
- Freeze transaction format.
- Freeze sighash.
- Freeze address types.
- Freeze fork-choice.
- Freeze consensus constants.

### M4.2 Governance

- Publish NIP-0001.
- Open public NIP discussion process.
- Approve genesis distribution.
- Define treasury controls.

### M4.3 Legal

- Decide US/MSB or explicit non-US posture.
- Counsel reviews terms, privacy, risk disclosures.
- Trademark decision.

### M4.4 Security

- External audit.
- Findings register.
- Critical/high fixes.
- Medium findings waived only with rationale.

### M4.5 Performance

Measure and record:

- block validation latency,
- memory,
- storage growth,
- restart replay,
- mempool behavior.

## Evidence files

```text
reports/m4_evidence/external_audit_completion.json
reports/m4_evidence/protocol_spec_freeze.json
reports/m4_evidence/consensus_change_signoff.json
reports/m4_evidence/genesis_distribution_approval.json
reports/m4_evidence/legal_posture_counsel_review.json
reports/m4_evidence/foundation_or_entity.json
reports/m4_evidence/trademark_status.json
reports/m4_evidence/performance_benchmark_report.json
reports/m4_evidence/cold_storage_ceremony.json
```

## Exit criteria

`make m4-rc-strict` passes.
