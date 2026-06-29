# NetCoin local deployment QA results

This QA pass exercises the local wallet, payment, merchant, operator, Phase 7, webhook, SQLite, and admin-auth flows that can be tested without external production services.

## What was checked

`tools/deployment_qa.py` currently verifies:

1. Create wallet.
2. Get faucet-style test coins from a local mined funding wallet.
3. Save a contact/known label and verify the browser wallet contact storage key exists.
4. Send a payment.
5. Create an invoice.
6. Pay the invoice.
7. View a receipt.
8. Create and verify a merchant API key.
9. Create a payout plan.
10. Approve a payout plan.
11. Export a signer bundle.
12. Record a signed transaction.
13. Record a broadcast txid.
14. Create a recurring payment agreement and invoice.
15. Create and approve a 2-of-3 escrow payout.
16. Create a poll and cast a signed-message vote.
17. Create, trade, and resolve a testnet/demo prediction market.
18. Deliver a signed webhook to a local capture server.
19. Reopen SQLite-backed app storage and confirm data persists.
20. Confirm admin routes reject requests without a token and accept the configured token.
21. Confirm the security status reports SQLite storage.

## Commands run in this pass

```bash
node --check webexplorer/public/admin-app.js
node --check webexplorer/public/explorer-app.js
node --check webwallet-browser/public/wallet-app.js
python -m py_compile netcoin/apps.py netcoin/node.py netcoin/explorer_server.py tools/verify_release.py tools/deployment_qa.py tools/operator_qa_smoke.py tools/run_test_suite_by_file.py
PYTHONPATH=. python tools/deployment_qa.py --json
PYTHONPATH=. python tools/operator_qa_smoke.py
PYTHONPATH=. pytest -q tests/test_deployment_qa.py tests/test_app_layer_phases.py tests/test_admin_operator_dashboard.py tests/test_phase7_hardening.py tests/test_phase7_app_layer.py tests/test_phase_finish_completion.py tests/test_explorer_server.py tests/test_node_api.py tests/test_browser_upgrade_assets.py tests/test_wallet_features.py tests/test_tools.py
```

Additional protocol/wallet/node tests were also run in smaller groups or individual files because the full `pytest -q` process and the by-file runner were killed by the local sandbox after partial progress. The same files that were split passed when run in smaller groups.

## Results

- Static JavaScript syntax checks passed.
- Python compile checks passed.
- `tools/deployment_qa.py --json` passed all 21 local deployment QA checks.
- `tools/operator_qa_smoke.py` passed: `1 passed`.
- Main app-layer/admin/wallet/explorer targeted regression group passed: `52 passed`.
- Broader protocol/wallet/node/explorer tests were run in split groups/individual files and passed in those runs.

## Bugs fixed during this pass

- Fixed invoice payment matching so a fresh invoice is not marked paid by older transactions that were already on the recipient address before the invoice was created.
- Added invoice creation height/time anchors: `created_height` and `watch_from_height`.
- Fixed the app-layer receipt router so `/api/receipt/<txid>` remains JSON while `/receipt/<txid>` remains the public HTML receipt page.
- Added merchant API-key header support to node app-layer POST routes.
- Hardened payout-plan lookup so team-wallet proposals stored as either dictionaries or lists can be reviewed/signed/broadcasted by the admin dashboard.
- Added/updated QA regression tests so invoices are created first and then paid by later transactions.

## Still outside local QA scope

These require real deployment infrastructure or external review:

- AWS DNS/CloudFront/S3 behavior.
- Real Discord and Telegram bot tokens.
- Email/web-push/Discord notification delivery.
- Production database backups and restore drills.
- Real hot-wallet or offline-signer operations.
- External security audit.
- Legal review before any public real-value prediction-market use.
