# Governance and Treasury

**Status:** scaffolded / default-off.

**Purpose:** Proposal lifecycle, voting rules, treasury multisig, public dashboard, spending audit trail, governance calendar, decision log, and emergency governance.

## Code anchors

- Module: `netcoin/competitive/governance.py`
- Config: `config/competitive/governance_treasury.json`
- Test: `tests/test_competitive_scaffold.py`

## Feature skeletons

### Proposal lifecycle states and metadata

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### On-chain/off-chain voting rules, quorum, periods, and snapshots

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Treasury multisig signer policy and rotation plan

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Public treasury dashboard feed

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Immutable spending audit trail

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Governance calendar and upgrade schedule

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Permanent decision log

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Emergency governance and critical-patch process

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

## Promotion checklist

- [ ] Owner assigned
- [ ] Threat/abuse cases documented
- [ ] Tests written
- [ ] Metrics/alerts added
- [ ] Docs published
- [ ] Rollback tested
- [ ] Security review completed


## Level-5 Baseline

This area has been promoted from scaffold-only to NetCoin's 5/10 midlevel baseline. The baseline means there are deterministic testnet/dev code hooks, validation helpers, operator controls, and smoke tests. It does not mean the area is externally audited, legally cleared, custody-ready, or mainnet-ready.

Acceptance requirements for the baseline:

- Feature rows report `midlevel_testnet` with `maturity_score: 5`.
- Area module exposes `default_controls()`, `feature_matrix()`, `readiness_gates()`, and `smoke_check()`.
- `python tools/competitive_gap_report.py --level5 --validate` must pass.
- Production claims remain blocked until independent audit and legal/security review are complete.
