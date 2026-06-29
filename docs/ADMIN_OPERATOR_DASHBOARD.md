# NetCoin Admin Operator Dashboard

The admin/operator dashboard is a protected browser UI for managing the app-layer features that were added on top of the NetCoin node and explorer.

Static UI files:

```text
webexplorer/public/admin.html
webexplorer/public/admin-app.js
```

Primary APIs:

```text
GET  /api/admin/summary
GET  /api/admin/payouts
GET  /api/admin/payouts/<payout_id>
GET  /api/admin/payouts/<payout_id>/bundle
POST /api/admin/payouts/<payout_id>/review
POST /api/admin/payouts/<payout_id>/reject
POST /api/admin/payouts/<payout_id>/signed
POST /api/admin/payouts/<payout_id>/broadcasted
GET  /api/security/status
GET  /api/security/audit
POST /api/merchant/webhook-events/deliver
```

## Recommended environment

Use SQLite and admin-token protection for any shared deployment:

```bash
export NETCOIN_APP_STORAGE=sqlite
export NETCOIN_APP_REQUIRE_ADMIN=1
export NETCOIN_APP_ADMIN_TOKEN='replace-with-a-long-random-secret'
export NETCOIN_REQUIRE_MARKET_LEGAL_ACK=1
```

The dashboard reads the token from a local browser field and sends it as:

```text
X-Netcoin-Admin-Token: <token>
```

Do not put the admin token into public source code, static files, GitHub Actions logs, S3 metadata, or CloudFront function config.

## Operator workflow

1. Open `admin.html` next to the hosted explorer.
2. Enter and save the admin token locally.
3. Review the operations summary.
4. Review pending payout plans.
5. Export the signer bundle for each approved payout.
6. Sign the bundle with a trusted NetCoin wallet or offline signing machine.
7. Broadcast the signed transaction through your own node.
8. Record the resulting txid back into the dashboard.
9. Check the audit log and webhook delivery state.

The dashboard is intentionally an operator tool, not a public app.

## Launch QA smoke test

Before publishing a new testnet build, run the automated operator checklist:

```bash
PYTHONPATH=. python tools/operator_qa_smoke.py
```

That smoke test creates a temporary chain and exercises the same launch flow an operator would manually click through:

1. create wallets and fund a wallet,
2. label a contact/address,
3. send a payment,
4. create and pay an invoice,
5. view a receipt,
6. create a merchant API key,
7. register and deliver a signed webhook,
8. create/review/sign/broadcast a payout plan through admin APIs,
9. create a recurring agreement,
10. create and release a 2-of-3 escrow,
11. vote in a signed-message poll,
12. create and resolve a demo prediction market,
13. check spending limits, backup health, PDF statements, SQLite persistence, and admin-token rejection.

For CI and constrained environments, run the whole test suite by file instead of one memory-heavy pytest process:

```bash
PYTHONPATH=. python tools/run_test_suite_by_file.py --timeout 180
```
