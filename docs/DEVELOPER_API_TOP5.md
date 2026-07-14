# NetCoin Developer API Top Five

These app-layer APIs let games and apps use NetCoin without changing consensus
or holding player private keys. Amounts are exact integer netoshis internally;
wallets and dashboards may display NET.

## 1. Rewards API

`POST /api/developer/rewards`

Creates a developer-funded reward record and an unsigned payout plan for manual
wallet signing.

```json
{
  "developer_id": "game-studio",
  "player_id": "player-7",
  "address": "net1...",
  "amount_sats": 2500,
  "event": "daily_quest",
  "idempotency_key": "daily-quest-player-7-20260714"
}
```

## 2. Withdrawals API

`POST /api/developer/withdrawals`

Records a player withdrawal request and returns an unsigned payout plan.

```json
{
  "developer_id": "game-studio",
  "player_id": "player-7",
  "address": "net1...",
  "amount": "0.01"
}
```

## 3. Payment Links

`POST /api/developer/payment-links`

Creates a hosted checkout link backed by the existing invoice engine.

```json
{
  "developer_id": "game-studio",
  "address": "net1...",
  "amount": "0.25",
  "title": "Starter pack"
}
```

## 4. Webhooks

`POST /api/developer/webhooks`

Registers signed callbacks for app events such as `reward.created`,
`withdrawal.created`, and `payment.confirmed`.

## 5. Developer Dashboard

`GET /api/developer/dashboard?developer_id=game-studio`

Returns counts, totals, recent rewards, recent withdrawals, payment links,
webhooks, and API usage.

## Safety Model

- NetCoin never needs a player private key.
- Rewards and withdrawals create unsigned payout plans first.
- Developers should use idempotency keys for reward and withdrawal retries.
- Tiny game balances should be accumulated off-chain until a withdrawal
  threshold is reached.

## Next Seven Developer Features

### Game Rewards SDK

`GET /api/developer/sdk`

Returns TypeScript, Python, and Unity/C# reference package metadata and snippets
for the Developer API.

### Address Watch API

`POST /api/developer/watch-addresses`

Registers an address for deposit monitoring.

`GET /api/developer/deposits?developer_id=game-studio`

Scans watched addresses and returns matching deposits, confirmations, and
readiness.

### Webhook Signature Verifiers

`GET /api/developer/webhook-verifiers`

Returns HMAC-SHA256 verifier snippets for signed NetCoin webhooks.

### Sandbox Developer Console

`GET /api/developer/console?developer_id=game-studio`

Combines dashboard, SDK, webhook verifier, deposit, and quick-action metadata
for a developer console.

### Unsigned Transaction Builder

`POST /api/developer/transactions/build`

Builds a non-custodial unsigned transaction draft from spendable UTXOs. The
developer or player signs locally before broadcast.

### Batch Payouts

`POST /api/developer/rewards/batch`

Creates one batch reward payout plan for many players.

### Developer Simulation Mode

`POST /api/developer/simulate/rewards`

Estimates reward totals, dust risk, fee pressure, and withdrawal-threshold
recommendations before spending coins.
