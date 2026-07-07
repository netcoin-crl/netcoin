# NetCoin Incident Response Runbook

## Severity Levels

- **SEV-1**: key compromise, consensus bug, chain halt, release compromise, active fund loss.
- **SEV-2**: major seed/explorer/faucet outage, API abuse, market integrity issue, serious data corruption.
- **SEV-3**: degraded endpoint, documentation error, isolated wallet issue, non-critical dashboard bug.

## First 15 Minutes

1. Identify affected component and freeze risky automation.
2. Preserve logs, chain data, release artifacts, and app-layer SQLite/JSON state.
3. Rotate exposed API/webhook/admin keys if compromise is possible.
4. Publish a short status note if public services are affected.
5. Assign an incident owner and scribe.

## Containment

- Disable faucet or reduce payout limits during abuse.
- Require admin tokens for app-layer writes during an attack.
- Pause prediction-market creation/resolution when integrity alerts are high.
- Stop release distribution if checksums or signing keys are suspect.
- Snapshot chain/app state before attempting repair.

## Recovery

- Reindex or restore from verified backups when storage corruption is detected.
- Rebuild releases using `tools/make_release.sh` and verify with `tools/verify_release.py`.
- Re-run focused tests and `python tools/professional_readiness.py --issues`.
- Document root cause, blast radius, and permanent fixes.

## Postmortem Template

- Incident summary
- Timeline with exact timestamps
- User impact
- Detection source
- Root cause
- What worked
- What failed
- Corrective actions with owners
- Follow-up tests added
