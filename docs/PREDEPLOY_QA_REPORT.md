# NetCoin pre-deployment QA report

This report records the automated launch-readiness QA pass for the admin/operator build.

## Confirmed issues fixed

1. `/api/receipt/<txid>` now returns JSON instead of the public HTML receipt page. Public `/receipt/<txid>` still returns HTML, and `/api/receipt/<txid>.pdf` still returns a PDF receipt.
2. The node app-layer POST handler now accepts merchant API keys from `X-Netcoin-Api-Key` or `X-API-Key`, matching the explorer handler behavior.
3. `/api/security/status` now includes `recommended_storage`, so operators can see that SQLite is the recommended app-layer backend.

## Added QA coverage

- `tests/test_operator_smoke_qa.py` automates the manual pre-deploy checklist:
  - wallet creation
  - faucet-like test funding
  - contact/label storage
  - sending a payment
  - invoice creation and payment
  - receipt JSON/HTML/PDF checks
  - merchant API key enforcement
  - webhook delivery with HMAC signature verification
  - manual payout plan review, signer bundle export, signed transaction record, and broadcast txid record
  - recurring payment agreements
  - 2-of-3 escrow release
  - signed-message poll flow
  - testnet prediction-market demo flow
  - SQLite persistence
  - admin/security summary checks
- `tools/deployment_qa.py` provides a local operator QA command for testnet deployments.
- `tests/test_deployment_qa.py` validates the deployment QA command.
- `tests/test_operator_manual_qa_smoke.py` validates the admin-token protected operator flow through HTTP APIs.

## Validation results

Static checks passed:

```bash
node --check webexplorer/public/admin-app.js
node --check webexplorer/public/explorer-app.js
node --check webwallet-browser/public/wallet-app.js
python -m py_compile netcoin/apps.py netcoin/node.py netcoin/explorer_server.py tools/verify_release.py
```

Deployment QA command passed with 21 checks:

```bash
python tools/deployment_qa.py --data-dir /tmp/netcoin-qa-cli-test --json
```

Pytest collection after this pass:

```text
364 tests collected
```

The complete test set was validated by running the test files in smaller batches. Running the whole suite as one sandbox command can exceed the sandbox runner's practical timeout, but the individual files and batches completed without failures.
