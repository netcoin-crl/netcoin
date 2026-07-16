# NetCoin v0.13 Batch Upgrade Report

This build adds four focused upgrade batches on top of the cleaned v0.13 professional code-upgrade baseline.

## Batch 1: Explorer + wallet safety

Added a production-style derived explorer indexer:

- `netcoin/indexer_storage.py`
- `netcoin/indexer.py`
- `netcoin/indexer_api.py`

The indexer builds normalized SQLite tables for blocks, transactions, address events, token events, market events, mempool entries, address history, transaction graph data, and reorg rollback.

Added wallet safety and recovery modules:

- `netcoin/tx_simulator.py`
- `netcoin/wallet_risk.py`
- `netcoin/recovery.py`

These provide transaction previews, fee/input/output/change summaries, frozen-coin warnings, dust warnings, address-reuse warnings, address-poisoning detection, seed verification, gap-limit scan previews, encrypted backup validation, and migration dry-runs.

Added browser E2E scaffolding:

- `playwright.config.js`
- `webwallet-browser/tests/e2e/wallet.spec.js`
- `sites/tests/e2e/markets.spec.js`

## Batch 2: Network + ops

Added persistent peer/network tooling:

- `netcoin/peerdb.py`
- `netcoin/sync.py`
- `netcoin/metrics.py`
- `ops/prometheus/netcoin-alert-rules.yml`

These provide a SQLite peer database, peer diversity keys, ban/discourage persistence, header sync/download scheduling, Prometheus-style metrics, alert evaluation, and alert rules for no peers, mempool spikes, and webhook dead letters.

## Batch 3: Markets Labs

Added stronger prediction-market support:

- `netcoin/apps/markets/oracles.py`
- `netcoin/apps/markets/mm.py`
- `netcoin/apps/markets/reconciliation.py`

New app-layer methods provide oracle registration, evidence submission, dispute comments, oracle dossiers, market-maker quote plans, and settlement reconciliation reports.

Updated Markets Labs UI:

- Evidence registry display
- Dispute/comment panel
- Evidence submission controls
- Dispute/comment controls

## Batch 4: Professional integrations

Added exchange/custody state machines:

- `netcoin/exchange.py`

This covers deposit states (`seen`, `confirming`, `credited`, `reorged`, `reversed`) and withdrawal states (`requested`, `approved`, `signed`, `broadcast`, `confirmed`, `failed`, `canceled`).

Added signed-envelope SDK helpers:

- `sdk/netcoin-python/netcoin_sdk.py`
- `sdk/netcoin-js/index.js`

Added OpenAPI contract tooling:

- `tools/check_openapi_contract.py`
- expanded market route docs in `docs/openapi.yaml` and `sites/api/openapi.yaml`

Added release signing/provenance helpers:

- `tools/sign_release.py`
- `tools/verify_signature.py`

## Verification

The new batch regression test is `tests/test_upgrade_batches.py`.

Validated commands:

```bash
python -m compileall -q netcoin tools
python -m pytest -q tests/test_upgrade_batches.py
python tools/professional_upgrade_audit.py --fail-on-issues
python tools/check_openapi_contract.py
make test-fast
node --check sites/markets/markets.js
node --check sdk/netcoin-js/index.js
```

This is still testnet/educational software and should not be treated as audited mainnet infrastructure.
