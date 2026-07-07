# Smart Contracts and Tokens

**Status:** scaffolded / default-off.

**Purpose:** Formal VM/execution model, gas metering, sandboxing, static analysis, source verification, events, upgrades, oracles, and token standards.

## Code anchors

- Module: `netcoin/competitive/contracts.py`
- Config: `config/competitive/smart_contracts_tokens.json`
- Test: `tests/test_competitive_scaffold.py`

## Feature skeletons

### Deterministic VM/execution-model design placeholder

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Gas/resource metering policy

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Contract sandboxing boundary

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Contract static analyzer rule registry

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Verified source registry and explorer integration plan

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Contract event log/indexing plan

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Contract upgrade and admin-safety policy

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Oracle design and risk registry

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Reentrancy/access-control/integer/randomness/DoS safety checklist

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Fungible and non-fungible token standards roadmap

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
