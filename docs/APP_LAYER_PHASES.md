# NetCoin Functional App-Layer Phases

This pass implements Phases 1–6 as app-layer features. They do not change consensus rules.

## Phase 1 — Payments foundation

Implemented through `netcoin/apps.py` and node/explorer routes:

- invoices/payment requests: `POST /api/invoices`
- invoice status: `GET /api/invoices/<invoice_id>` and `GET /api/checkout/<invoice_id>`
- transaction receipts: `GET /api/receipt/<txid>`
- address validation: `GET /api/validate-address?address=<addr>`
- CSV sales export: `GET /api/merchant/export.csv`

## Phase 2 — Usability

- local username/profile registry: `/api/usernames`, `/api/profiles/<name>`
- shareable profile/receive data
- known labels endpoint
- JavaScript and Python SDK starters

## Phase 3 — Merchant tools

- one-time API key generation: `POST /api/merchant/api-keys`
- webhook registration: `POST /api/merchant/webhooks`
- webhook event queue: `POST /api/merchant/webhook-events`
- refund records: `POST /api/merchant/refunds`
- sales CSV export
- browser explorer merchant dashboard

## Phase 4 — Community

- gift links: `POST /api/community/gifts`, `POST /api/community/gifts/claim`
- airdrop dry-run validator: `POST /api/community/airdrops`
- bounty board: `POST /api/community/bounties`
- bounty submissions/awards
- leaderboards: `GET /api/community/leaderboards`
- Discord/Telegram tip-bot starter folders

## Phase 5 — Wallet power tools

- transaction categories: `POST /api/wallet/categories`
- wallet statement JSON/CSV: `/api/wallet/statement`, `/api/wallet/statement.csv`
- balance alerts: `POST /api/wallet/alerts`
- spending limits/savings mode: `POST /api/wallet/limits`
- backup health records: `POST /api/wallet/backup-health`
- team wallet records: `POST /api/wallet/team-wallets`
- browser wallet panel for reports, alerts, limits, and backup status

## Phase 6 — Explorer/network utility

- known address labels: `POST /api/labels`
- network health dashboard: `GET /api/network`
- mining dashboard: `GET /api/mining/dashboard`
- mining calculator: `GET /api/mining/calculator?hashrate=...`
- node map: `GET /api/node-map`
- reward countdown: `GET /api/reward-countdown`
- treasury transparency: `GET/POST /api/treasury`

## Storage

Data is stored in `<data_dir>/app_layer.json`. This is suitable for a local/testnet operator. A production deployment should migrate this schema to SQLite/PostgreSQL, add authentication for write endpoints, and restrict merchant/community admin operations.

## Phase 7 — Programmable app-layer contracts

This pass adds Phase 7 as app-layer state and APIs. These features are intentionally **not consensus-rule changes** yet; they let operators and users test contract workflows before any protocol-level enforcement.

### Smart-contract template registry

- `GET /api/contracts/templates` — list supported templates.
- `GET /api/contracts` — list created contract records.
- `POST /api/contracts` — create generic template-backed records.
- `POST /api/contracts/<contract_id>/transition` — record a safe app-layer state transition.

Initial templates:

- `timelock`
- `vesting`
- `multisig`
- `escrow_2_of_3`
- `recurring_payment`
- `poll`
- `prediction_market`

### Recurring payment agreements

- `GET /api/recurring`
- `POST /api/recurring`
- `POST /api/recurring/<agreement_id>/invoice`
- `POST /api/recurring/<agreement_id>/payment`
- `POST /api/recurring/<agreement_id>/action`

The first implementation is non-custodial: it creates due invoices and records user-approved payments. It does not automatically spend from a wallet.

### Escrow contracts

- `GET /api/escrows`
- `GET /api/escrows/<escrow_id>`
- `POST /api/escrows`
- `POST /api/escrows/<escrow_id>/action`

Escrow is modeled as a 2-of-3 multisig agreement between buyer, seller, and mediator. Two matching approvals create a payout plan for wallet signing.

### Signed-message polls / voting

- `GET /api/polls`
- `GET /api/polls/<poll_id>`
- `POST /api/polls`
- `POST /api/polls/<poll_id>/vote`
- `POST /api/polls/<poll_id>/close`

Votes use the message format:

```text
NetCoin poll:<poll_id>:vote:<option_id>
```

The API verifies NetCoin signed messages when a signature is supplied. Local demo votes may set `allow_unverified_demo` for testing only.

### Prediction-market demo

- `GET /api/markets`
- `GET /api/markets/<market_id>`
- `POST /api/markets`
- `POST /api/markets/<market_id>/order`
- `POST /api/markets/<market_id>/resolve`

Prediction markets are restricted to `testnet_demo`, `play_money`, or `private_dev` modes. They support YES/NO or multi-outcome market records, a basic order book, matched trades, positions, manual oracle resolution, and payout-plan creation. Do not use this for real-money regulated event contracts without legal review and production custody/security work.

### Explorer UI

The static explorer now includes a **Phase 7** tab for:

- viewing available templates
- creating timelocks and multisig template records
- creating recurring agreements
- creating 2-of-3 escrow records
- creating polls
- creating, trading, and resolving testnet/play-money prediction market demos

## Phase 7 hardening pass

This pass adds production-safety hooks around the Phase 7 app layer. These do not replace a legal/security review, but they make the code safer to deploy for testnet/private environments.

### Optional SQLite app-layer storage

By default the app layer keeps using `<data_dir>/app_layer.json` for local development. Operators can switch to SQLite without changing API code:

```bash
NETCOIN_APP_STORAGE=sqlite python -m netcoin.explorer_server --data <data_dir>
```

When SQLite is enabled, state is stored in `<data_dir>/app_layer.sqlite3`. If an existing JSON state file exists, the first SQLite load migrates it into the SQLite `app_state` table. The SQLite backend also keeps an `app_audit` table for operator/security events.

### Admin token gate

Write endpoints can be locked behind an operator token:

```bash
NETCOIN_APP_REQUIRE_ADMIN=1
NETCOIN_APP_ADMIN_TOKEN='replace-with-long-random-token'
```

Clients then send:

```text
X-Netcoin-Admin-Token: replace-with-long-random-token
```

This protects app-layer write routes such as invoices, merchant operations, community tools, contracts, recurring agreements, escrows, polls, and prediction markets. It also protects sensitive operator reads under `/api/merchant`, `/api/wallet`, `/api/custody`, and `/api/security`.

### Merchant API keys from headers

Merchant API keys may now be passed with:

```text
X-Netcoin-Api-Key: nck_...
```

The server injects that into the app-layer request body when the body does not already contain `api_key`. Merchant-specific enforcement still depends on setting `api_key_required` for that merchant.

### Webhook retry/dead-letter behavior

Webhook delivery now records:

- `attempt_count`
- `last_attempt_at`
- `next_attempt_at`
- per-attempt status/error
- `dead_letter` after the webhook's `max_attempts`

Webhook deliveries use HMAC signatures in `X-Netcoin-Signature`. Operators can call:

```text
POST /api/merchant/webhook-events/deliver
```

with `force=true` or `redeliver=true` for maintenance/testing.

### Custody/signing policy

Payout plans now include the current signing policy and whether operator review is required. The policy is available at:

```text
GET  /api/custody/policy
POST /api/custody/policy
```

Default policy is manual wallet signing with hot-wallet auto-broadcast disabled. Enabling hot-wallet mode requires `acknowledge_hot_wallet_risk=true`.

### Prediction-market safety gates

Prediction markets remain restricted to:

```text
testnet_demo
play_money
private_dev
```

Operators can require an explicit legal/safety acknowledgement before market creation:

```bash
NETCOIN_REQUIRE_MARKET_LEGAL_ACK=1
```

When enabled, `POST /api/markets` must include:

```json
{"legal_acknowledged": true}
```

Restricted topics such as elections and sports betting require `operator_override=true` and should not be enabled without legal review.

### Security status endpoints

```text
GET /api/security/status
GET /api/security/audit
```

These expose storage backend, admin-token status, prediction-market acknowledgement mode, payout signing policy, and recent admin/security events.

## Admin/operator dashboard and manual payout signing

The hardened build includes an operator dashboard for managing app-layer state and payouts.

Static files:

```text
webexplorer/public/admin.html
webexplorer/public/admin-app.js
```

Public landing page from the live explorer server:

```text
GET /admin
```

Protected JSON APIs:

```text
GET  /api/admin/summary
GET  /api/admin/payouts
GET  /api/admin/payouts/<payout_id>
GET  /api/admin/payouts/<payout_id>/bundle
POST /api/admin/payouts/<payout_id>/review
POST /api/admin/payouts/<payout_id>/reject
POST /api/admin/payouts/<payout_id>/signed
POST /api/admin/payouts/<payout_id>/broadcasted
```

Payout plans now move through the manual signer flow:

```text
pending_operator_review
ready_for_wallet_signing
signed_ready_to_broadcast
broadcast_recorded
rejected
```

The dashboard also provides quick access to security status, audit events, and webhook retry delivery.
