# NetCoin M1 Incident Response Runbook

Status: M1 public-testnet runbook. This document is an operator playbook for the current testnet. It does **not** claim mainnet readiness, legal/compliance coverage, external audit completion, or a 24/7 staffed security operations center.

## Scope

Use this runbook for incidents affecting the NetCoin public testnet, static sites, faucet, explorer, API, seed nodes, release artifacts, or public communications.

Out of scope for automatic action:

- Consensus, emission schedule, address format, or monetary-policy changes.
- Deployments to seed1, seed2, or seed3 without explicit human approval.
- Secret rotation steps that require real credentials in a chat transcript or committed file.
- Mainnet, exchange, market-maker, or legal incident handling.

## Roles

| Role | Responsibility |
| --- | --- |
| Incident owner | Makes final calls, freezes risky changes, decides when to communicate publicly. |
| Scribe | Maintains the timestamped timeline and captures commands, links, and observations. |
| Operator | Runs local checks, seed health checks, backups, deploy/rollback commands when approved. |
| Communicator | Posts status updates and keeps the public message short, factual, and non-speculative. |
| Reviewer | Reviews the fix before it is merged or deployed. For consensus-adjacent work, this must be a second set of eyes. |

For the current solo/small-team phase, the same person may hold multiple roles, but every incident must still name an owner and scribe.

## Severity levels

| Severity | Examples | Public communication target |
| --- | --- | --- |
| SEV-1 | Key compromise, release compromise, consensus bug, chain halt, active fund loss, faucet draining at scale. | Initial public note within 15 minutes if users or public services are affected. |
| SEV-2 | Major seed/explorer/faucet/API outage, data corruption, significant abuse, broken wallet release, bad deploy. | Initial public note within 30 minutes if the service remains affected. |
| SEV-3 | Degraded endpoint, stale status panel, isolated UI bug, documentation error, non-critical dashboard issue. | Public note optional; track in issue/handoff if user-visible. |

## First 15 minutes

1. Name the incident owner and scribe.
2. Stop risky automation. Do not deploy, restart systemd, rotate secrets, or change DNS unless the owner explicitly approves it.
3. Identify affected component: wallet, faucet, explorer, API, status, seed node, release artifact, docs, or public site.
4. Preserve evidence before changing state:
   - failing command output,
   - browser console/error screenshot,
   - relevant logs,
   - current HEAD and package checksum,
   - chain height and peer count,
   - faucet queue/status if affected.
5. Classify severity as SEV-1, SEV-2, or SEV-3.
6. If public service is affected, post a short status note using the template below.
7. Create a working branch or local patch; never hot-edit seed files from chat instructions.

## Triage commands

Run only the commands relevant to the affected component.

```bash
# Repo state before touching files
git rev-parse HEAD
git status --short
git log --oneline -5

# Local M1 source checks
python3 tools/check_m1_readiness.py --out reports/m1_readiness_source_report.json
python3 tools/run_m1_release_candidate.py --profile source --out reports/m1_release_candidate_report.json --stop-on-fail
python3 tools/check_site_ui_polish.py

# Browser/accessibility checks before a web-facing fix is considered ready
python3 tools/run_browser_e2e_matrix.py --run-playwright
python3 tools/run_accessibility_matrix.py --strict

# Live public check from networks that block netcoin.online directly
curl -sk -H 'Host: status.netcoin.online' https://18.220.89.128/ | head -6
curl -sk -H 'Host: api.netcoin.online' https://18.220.89.128/api/health
curl -sk -H 'Host: explorer.netcoin.online' https://18.220.89.128/api/fee-estimates
```

Do not run unattended `sudo systemctl` commands on live seeds from an incident draft. If a service restart is required, write the exact command in the incident notes and wait for human approval.

## Containment playbooks

### Wallet UI or SRI failure

- Do not weaken CSP or remove SRI.
- Recompute SRI for `sites/wallet/wallet-app.js` if that file changed.
- Update both wallet HTML references and cache-busters.
- Run wallet JS syntax checks and browser E2E.
- Roll back with the previous wallet asset set if the browser refuses to load the app.

### Faucet abuse or CAPTCHA failure

- Never commit real Turnstile/hCaptcha secrets.
- Temporarily lower payout limits or raise cooldowns through environment/config only.
- If CAPTCHA validation is broken, disable claims or require admin review rather than allowing unprotected automated claims.
- Preserve faucet state and abuse counters before clearing queues.

### Explorer/API outage

- Check static fallbacks before assuming node failure.
- Compare `/api/health`, `/api/latest?n=1`, `/api/mempool?transactions=0`, and `/api/peers`.
- If live API is down but static status is healthy, classify the incident as API/runtime rather than site shell.

### Seed node issue

- Canary seed3 before seed2 or seed1 for any approved deploy.
- Clean `/tmp/tmp.*` and prune old backups before copying artifacts.
- Never touch seed1 ports `3000`, `8000`, or `8501`.
- If chain data corruption is suspected, preserve the corrupt directory before redeploying.

### Release artifact or checksum issue

- Stop distribution immediately.
- Preserve the suspect artifact and checksum.
- Rebuild locally using the documented release path.
- Re-run source, strict, browser, accessibility, parity, Rust, and TypeScript gates before publishing replacement artifacts.

## Public communication templates

### Initial note

```text
NetCoin testnet status: investigating <component>. Impact: <known user impact>. We have frozen risky changes while we preserve logs and confirm root cause. Next update by <time>. This affects the public testnet only; no mainnet is live.
```

### Update note

```text
NetCoin testnet status update: <component> is <recovering/degraded/unavailable>. Current finding: <one factual sentence>. Mitigation: <what changed or what remains frozen>. Next update by <time>.
```

### Resolution note

```text
NetCoin testnet status resolved: <component> recovered at <time>. Root cause summary: <one factual sentence>. Follow-up: <test/runbook/change added>. A postmortem will be added if this was SEV-1 or SEV-2.
```

## Recovery checklist

Before declaring recovery:

- The incident owner confirms user-visible behavior is restored or explicitly degraded.
- The scribe records exact recovery time.
- Relevant local checks pass.
- Any rollback/deploy commands are recorded.
- Public communication is updated if public users were affected.
- Follow-up tests or runbook changes are opened as tasks.

## Postmortem template

Use this for every SEV-1 and user-visible SEV-2.

```markdown
# Incident postmortem: <title>

- Severity:
- Incident owner:
- Scribe:
- Started:
- Detected by:
- Resolved:
- Affected components:
- User impact:

## Timeline

- <timestamp> — <fact>

## Root cause

<Write the technical cause in plain language. Do not speculate without labeling it.>

## What worked

- ...

## What failed

- ...

## Corrective actions

| Action | Owner | Due | Verification |
| --- | --- | --- | --- |
| ... | ... | ... | ... |

## Follow-up tests added

- ...
```

## Exit criteria for this M1 runbook

This runbook is M1-complete when:

- severity levels are documented,
- owner/scribe/operator/communicator roles are documented,
- first-15-minute steps are documented,
- containment playbooks exist for wallet, faucet, explorer/API, seed, and release incidents,
- public communication templates exist,
- recovery and postmortem templates exist,
- the status site links to incident response guidance,
- the offline M1 readiness gate checks these markers.
