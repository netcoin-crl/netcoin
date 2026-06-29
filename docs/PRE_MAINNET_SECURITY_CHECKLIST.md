# Pre-Mainnet Security Checklist

Do not launch NetCoin mainnet or real-value app-layer services until this checklist is complete.

## Repository and releases

- [ ] All code is pushed to GitHub.
- [ ] CI passes on every pull request.
- [ ] Dependency audit passes.
- [ ] Release artifacts have SHA256 checksums.
- [ ] Release checksums are GPG-signed.
- [ ] Operators know how to verify release artifacts.

## Node and consensus

- [ ] Consensus code has a dedicated review.
- [ ] Reorg, mempool, signature, serialization, and script tests pass.
- [ ] Fuzz/adversarial tests have been run.
- [ ] Block/transaction validation invariants are documented.
- [ ] Node RPC/API is not exposed without protection.

## Wallet

- [ ] Wallet backups are tested from scratch.
- [ ] Private keys never leave the browser unless exported by the user.
- [ ] Send flow has clear confirmation and address validation.
- [ ] Spending limits and backup warnings work.
- [ ] Recovery process is documented.

## App-layer admin/security

- [ ] `NETCOIN_APP_STORAGE=sqlite` is used in deployment.
- [ ] `NETCOIN_APP_REQUIRE_ADMIN=1` is enabled.
- [ ] `NETCOIN_APP_ADMIN_TOKEN` is strong and secret.
- [ ] Admin dashboard is not indexed or publicly linked as a user feature.
- [ ] CORS is locked down.
- [ ] HTTPS is required.
- [ ] Rate limits are enabled.
- [ ] Logs do not contain secrets.

## Payouts and custody

- [ ] Manual payout signing is the default.
- [ ] Hot wallet is disabled unless separately audited.
- [ ] Payout plans require operator review.
- [ ] Signed tx artifacts and txids are recorded.
- [ ] Withdrawal/payout limits are defined.
- [ ] Incident response plan exists for wrong payouts or key compromise.

## Merchants and webhooks

- [ ] API keys are created securely and rotated when needed.
- [ ] Webhook signatures are verified by merchant examples.
- [ ] Webhook retry/dead-letter monitoring is active.
- [ ] Failed webhooks are visible to operators.
- [ ] Refund flow requires manual review.

## Prediction markets / polls

- [ ] Prediction markets are testnet/play-money only unless legal review is complete.
- [ ] `NETCOIN_REQUIRE_MARKET_LEGAL_ACK=1` is enabled.
- [ ] Restricted topics are blocked unless operator override is intentionally used.
- [ ] Market resolution rules are documented before market creation.
- [ ] Oracle/resolver policy is documented.

## Monitoring and backups

- [ ] Node uptime is monitored.
- [ ] Explorer/API uptime is monitored.
- [ ] Faucet balance is monitored.
- [ ] SQLite database backups are automated.
- [ ] Backup restore has been tested.
- [ ] Disk usage and logs are monitored.

## Legal and public communication

- [ ] Terms/disclaimer are published.
- [ ] Testnet/demo status is visible if not mainnet.
- [ ] Prediction-market limitations are visible.
- [ ] External security audit is scheduled or complete.
- [ ] Bug-report/security-contact process is public.

## Required automated QA commands

Run these before any public testnet refresh or release tag:

```bash
node --check webexplorer/public/admin-app.js
node --check webexplorer/public/explorer-app.js
node --check webwallet-browser/public/wallet-app.js
python -m py_compile netcoin/apps.py netcoin/node.py netcoin/explorer_server.py tools/verify_release.py tools/run_test_suite_by_file.py tools/operator_qa_smoke.py
PYTHONPATH=. python tools/operator_qa_smoke.py
PYTHONPATH=. python tools/run_test_suite_by_file.py --timeout 180
```

The by-file test runner is now used in CI because the full app/protocol suite can be memory-heavy when run in one long pytest process.
