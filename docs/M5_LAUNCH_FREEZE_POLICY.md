# M5 Launch Freeze Policy

Status: **source-ready, evidence required**.

At T-4 weeks, NetCoin enters launch freeze. This policy prevents last-minute risk from entering a mainnet launch candidate.

## Allowed during freeze

- Critical/high security fixes.
- Release signing fixes.
- Deterministic build fixes.
- Documentation corrections.
- Operator runbook corrections.
- Launch evidence corrections.
- Bug fixes with targeted tests.

## Not allowed during freeze

- New features.
- Consensus changes without NIP/signoff.
- Emission, address-format, genesis-economics changes.
- UI redesigns not needed for launch safety.
- Deployment automation that bypasses operator approval.

## Required evidence

Freeze is not active until `reports/m5_evidence/feature_freeze.json` records:

- frozen commit,
- allowed-change policy,
- approvers,
- freeze start time,
- rollback/halt policy.
