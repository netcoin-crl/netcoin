# NetCoin v0.13 Upgrade Layer Plus

This layer continues the previous batch upgrades with operator- and user-facing
features that improve existing systems instead of adding unrelated product areas.

## Added

- `netcoin/explorer_watch.py` — explorer watchlists and idempotent notifications for addresses, transactions, and blocks.
- `netcoin/wallet_approvals.py` — persistent wallet approval queue backed by tamper-evident approval receipts.
- `netcoin/ops_runbooks.py` — redacted diagnostic bundles and action recommendations from alerts/runbooks.
- `netcoin/apps/markets/integrity.py` — market integrity scoring, self-trade detection, cancel-rate checks, and dispute timelines.
- `netcoin/exchange_reserves.py` — Merkle liability tree, customer proofs, and proof-of-reserves attestation verification.
- `tools/generate_ops_bundle.py` — direct CLI helper for operations support bundles.
- `tools/generate_reserve_attestation.py` — direct CLI helper for reserve attestations.

## Verification

Run:

```bash
python -m compileall -q netcoin tools
python -m pytest -q tests/test_upgrade_layer_plus.py
python tools/professional_upgrade_audit.py --fail-on-issues
make test-fast
make ops-bundle
```

These features are still testnet/application infrastructure. They improve
readiness and operator safety but do not replace external audits, real custody
controls, or hostile network testing.
