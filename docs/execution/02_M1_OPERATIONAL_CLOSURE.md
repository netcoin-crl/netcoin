# M1 — Operational Closure Plan

## Goal

A stranger can open the product, create a wallet, get testnet coins, send/receive, and verify activity without manual help.

## Current source status

M1 source is considered near-complete or complete after the clean baseline. Remaining work is operational.

## Workstreams

### M1.1 Live deployment verification

- Deploy static/site-safe changes manually.
- Do not restart node services unless explicitly required.
- Verify wallet, faucet, explorer, status, docs, markets.

Evidence:

```text
reports/m1_evidence/live_smoke_report.json
```

### M1.2 CAPTCHA production configuration

- Choose Turnstile or hCaptcha.
- Configure secrets outside git.
- Confirm backend rejects missing/invalid challenge.
- Confirm status metadata does not leak secrets.

Evidence:

```text
reports/m1_evidence/captcha_production_config.json
```

### M1.3 Tester pilot

- Recruit 5–10 testers.
- Ask each tester to complete the wallet → faucet → explorer → status loop.
- Record friction.
- Fix blockers only; defer nice-to-haves.

Evidence:

```text
reports/m1_evidence/tester_pilot_summary.json
docs/execution/evidence/M1_TESTER_FEEDBACK_LOG.md
```

## Exit criteria

- Live smoke passes.
- CAPTCHA works with real provider secret.
- At least 5 testers complete the loop.
- No P0/P1 tester blockers remain.
