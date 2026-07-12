# NetCoin M1 Two-Week Testnet Pilot Plan

This is the operator-facing plan for running the first small public-testnet pilot after the M1 source and strict gates pass. It turns the roadmap sub-goal "5-10 friends actively use the wallet for two weeks" into a repeatable checklist.

NetCoin is public testnet software. Testnet NET has no real-money value, this plan does not claim mainnet readiness, and testers must never share seed phrases, private keys, CAPTCHA secrets, API keys, or screenshots containing full recovery words.

## Entry criteria

Do not invite testers until all of these are true:

- `make m1-rc-check` passes in the real checkout.
- `make m1-rc-strict` has been run locally and any failures are either fixed or explicitly recorded in the handoff.
- Wallet, Faucet, Explorer, and Status load through the production Host-header checks.
- The incident-response runbook owner/scribe/operator/communicator roles are assigned for the pilot window.
- The feedback intake page and `docs/TESTNET_FEEDBACK_LOG.md` are ready to capture one friction point per row.
- No real CAPTCHA secret, API key, seed phrase, private key, or admin token is committed to the repository.

## Pilot cohort

Start with 5 testers and only expand to 10 if the first 48 hours produce no P0/P1 blockers.

| Slot | Tester type | Device/browser target | Goal |
| --- | --- | --- | --- |
| 1 | Non-technical friend | iPhone Safari | Prove the wallet flow is understandable. |
| 2 | Non-technical friend | Android Chrome | Catch mobile layout and touch-target issues. |
| 3 | Technical friend | Desktop Chrome | Capture console/network errors quickly. |
| 4 | Technical friend | Desktop Firefox | Check browser compatibility. |
| 5 | Operator-adjacent tester | Laptop Safari or Edge | Verify restore/lock/unlock and status fallback clarity. |

## Required tester loop

Each tester should complete the same loop at least twice during the two-week pilot:

1. Create a fresh testnet wallet.
2. Copy a receive address.
3. Claim faucet NET.
4. Confirm the incoming transaction in Explorer.
5. Send a tiny payment.
6. Lock and unlock the wallet.
7. Check Status when anything is slow or unclear.
8. File feedback using the M1 intake template.

## Daily operating rhythm

| Day range | Operator focus | Exit signal |
| --- | --- | --- |
| Day 0 | Run gates, verify live Host-header checks, invite first 5 testers. | No gate failure is hidden or hand-waved. |
| Days 1-3 | P0/P1 blockers only. Do not add features. | Every P0/P1 has owner, disposition, and retest plan. |
| Days 4-7 | Fix the highest-frequency P2 usability friction. | Testers can finish the loop without direct coaching. |
| Days 8-10 | Mobile and accessibility retests. | iPhone Safari and Android Chrome loops pass. |
| Days 11-14 | Regression pass and closeout report. | All accepted P0/P1 are fixed or explicitly documented as release blockers. |

## Stop conditions

Pause the pilot if any of these happen:

- A tester exposes a seed phrase, private key, API key, CAPTCHA secret, or admin token.
- Wallet creation, unlock, send review, or lock/unlock fails for more than one tester.
- Faucet abuse or cooldown bypass is observed.
- Explorer or Status reports dangerously stale or false information.
- Any live incident reaches SEV-1 in `docs/INCIDENT_RESPONSE.md`.

## Closeout report template

```text
Pilot window:
Tester count:
Devices/browsers covered:
Completed wallet -> faucet -> explorer -> status loops:
P0 opened / closed:
P1 opened / closed:
P2 opened / closed:
P3 opened / closed:
Top 5 friction points:
Retest evidence:
Remaining blockers:
Decision: expand testers / fix blockers / do not proceed
```

## What this does not claim

This pilot plan does not claim live seed deployment, independent-node decentralization, external audit completion, hardware wallet support, mainnet readiness, real-money safety, real CAPTCHA credentials in source control, or that M1 is complete before the two-week loop produces clean evidence.
