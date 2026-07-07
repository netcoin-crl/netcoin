# App-Layer API Professionalization

**Status:** scaffolded / default-off.

**Purpose:** Signed writes, replay/idempotency protection, scoped API keys, usage dashboards, webhooks, RBAC, audit logs, and OpenAPI scaffolds.

## Code anchors

- Module: `netcoin/competitive/api.py`
- Config: `config/competitive/api_app_layer.json`
- Test: `tests/test_competitive_scaffold.py`

## Feature skeletons

### Mandatory signed writes for sensitive endpoints

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Global nonce replay protection coverage map

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Global idempotency-key coverage map

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Scoped API key model for read/write/admin/market/faucet actions

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Per-key API usage dashboard and export

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Webhook HMAC signing and verification contract

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Webhook retry log and manual replay workflow

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Role-based admin permissions

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Immutable audit log for sensitive actions

- Current state: scaffolded only.
- Default behavior: disabled in production and testnet-safe by default.
- Acceptance criteria before promotion:
  - Implementation exists behind a safe gate.
  - Unit, integration, and negative tests exist.
  - Operational runbook and rollback steps exist.
  - Security review/audit has no unresolved critical or high findings.

### Complete OpenAPI schema and example set

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
