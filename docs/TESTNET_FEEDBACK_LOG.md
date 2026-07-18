# NetCoin M1 Testnet Feedback Log

This is the operator-facing intake template for the two-week M1 tester loop. It turns tester friction into reproducible bugs instead of chat fragments.

NetCoin is public testnet software. Testnet NET has no real-money value, this package does not claim mainnet readiness, and no tester should share a seed phrase, private key, CAPTCHA secret, API key, or full recovery-word screenshot.

## How to use this log

1. Create one row per friction point, not one row per tester.
2. Keep the original tester wording in the Notes column when it is safe.
3. Redact secrets before pasting screenshots, console output, or request payloads.
4. Link every accepted bug to a GitHub issue or `BUG_INDEX.md` entry.
5. Re-test the fixed path before closing the row.

## Intake fields

| Field | What to capture | Example |
| --- | --- | --- |
| ID | Stable local tracker ID | `M1-FB-001` |
| Date | UTC date of report | `2026-07-11` |
| Tester | Initials or alias only | `tester-a` |
| Device/browser | OS, device, browser version if known | `iPhone Safari 18` |
| Surface | Wallet, Faucet, Explorer, Status, Docs | `Wallet` |
| URL | Exact page or route | `https://wallet.netcoin.online` |
| Action | What the tester tried | `Clicked Send after faucet claim` |
| Expected | What should have happened | `Review screen opens` |
| Actual | What happened instead | `Button disabled with no message` |
| Status snapshot | Height, mempool, peer count, uptime if relevant | `height stale, peers=1` |
| Evidence | Safe screenshot, console line, or txid | `redacted screenshot` |
| Severity | P0/P1/P2/P3 | `P1` |
| Owner | Person debugging | `maintainer` |
| Disposition | accepted / duplicate / cannot reproduce / docs-only | `accepted` |
| Fix link | PR, commit, issue, or patch | `pending` |
| Retest result | pass/fail with date | `pending` |

## Severity guide

- **P0:** Seed phrase/private key exposure, wallet cannot create/unlock, funds cannot be sent, faucet is openly abusable, or status/explorer gives dangerously false information.
- **P1:** A first-time tester cannot finish wallet -> faucet -> explorer -> status without help.
- **P2:** Confusing copy, mobile layout issue, missing feedback state, slow path, or recoverable error.
- **P3:** Cosmetic issue, typo, or improvement that does not block the loop.

## Copy-paste bug template

```text
ID:
Date UTC:
Tester alias:
Device/browser:
Surface:
URL:
Action:
Expected result:
Actual result:
Status snapshot if relevant:
Safe evidence:
Severity:
Owner:
Disposition:
Fix link:
Retest result:
```

## Two-week tester cadence

- Day 0: run `make m1-rc-strict`, follow `docs/TESTNET_PILOT_PLAN.md`, deploy only after an explicit operator decision, then invite testers.
- Days 1-3: collect P0/P1 issues only; fix blockers before expanding the tester group.
- Days 4-10: collect P2/P3 friction and usability notes; batch fixes into small patches.
- Days 11-14: run the complete journey again on desktop and mobile; only close M1 when the loop works without manual operator help.

## What this does not claim

This log does not claim live seed deployment, independent-node decentralization, external audit completion, hardware wallet support, mainnet readiness, or real-money safety.
