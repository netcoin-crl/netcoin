# M5 Rollback and Halt Policy

Status: **source-ready, evidence required**.

Mainnet launch can be halted before genesis. After genesis, rollback is a governance and incident-response event, not a casual deploy action.

## Halt before genesis

Halt if:

- hashes mismatch,
- signatures fail,
- audit/legal evidence missing,
- independent miners withdraw,
- node readiness falls below threshold,
- a critical bug appears.

## After genesis

Do not silently rewrite history. Any emergency checkpoint, hard fork, or client patch requires:

- public incident entry,
- explicit owner,
- public rationale,
- independent operator communication,
- postmortem.

Evidence files:

- `reports/m5_evidence/oncall_rotation.json`
- `reports/m5_evidence/incident_log.json`
