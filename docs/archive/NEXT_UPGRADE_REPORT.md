# NetCoin v0.13 Next Upgrade Report

This pass adds a second continuation layer focused on improving existing user-facing and operator-facing systems without changing consensus rules.

## Added modules

- `netcoin.indexer_insights`: explorer search suggestions, address heatmaps, counterparties, address profile bundles, CSV history export.
- `netcoin.wallet_policy`: wallet policy profiles, approval requests, approval receipts, and receipt verification.
- `netcoin.ops_incidents`: persistent incident store and alert-to-runbook workflow.
- `netcoin.apps.markets.governance`: oracle quorum voting and dispute escalation planning.
- `netcoin.exchange_accounting`: double-entry accounting ledger for exchange deposits/withdrawals and hot-wallet reconciliation.
- `tools/upgrade_healthcheck.py`: import/smoke healthcheck for the new upgrade modules.

## Upgrade impact

- Explorer: better search, richer address detail pages, and support/debug exports.
- Wallet: transaction approvals can be policy-based and saved as tamper-evident receipts.
- Ops: alerts can become persistent incidents with acknowledgement, resolution, and runbook steps.
- Markets: disputed resolutions can use oracle vote quorum and escalation rules.
- Exchange integrations: deposits and withdrawals can be mirrored into a balanced accounting ledger.
