# Product, Website, and Trust

**Status:** scaffolded / default-off.

**Purpose:** Roadmap, security/download pages, transparency, risk disclosures, legal disclaimers, changelog, FAQ, miner guide, and node-operator guide.

## Code anchors

- Module: `netcoin/competitive/product.py`
- Config: `config/competitive/product_trust.json`
- Test: `tests/test_competitive_scaffold.py`

## Feature skeletons

### Public roadmap with status and dates

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Security page with disclosure policy and audit status

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Download verification page for checksums/signatures

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Project transparency page for maintainers and governance roles

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Consistent testnet/educational/no-real-value risk disclosures

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Brand/legal disclaimer registry across public pages

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Public changelog grouped by release

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### FAQ for wallet/mining/faucet/markets/safety/testnet

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Miner setup and troubleshooting guide

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Node operator install/upgrade/monitor/recover guide

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
