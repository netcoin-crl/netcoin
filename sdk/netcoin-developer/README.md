# @netcoin/developer

Thin client for the NetCoin developer/app-layer API (`/api/developer/*`) — rewards,
batch rewards, withdrawals, funding-policy spend limits, payment links, webhooks,
watch-addresses/deposit detection, and simulate/build helpers for game studios
and apps.

This package is not published to npm yet — install it directly from the repo
until a registry release exists:

```
npm install github:netcoin-crl/netcoin#path:sdk/netcoin-developer
```

**Non-custodial by design.** Rewards and withdrawals never auto-broadcast —
every write returns an *unsigned* payout plan for a human or wallet to review
and sign.

```js
import { NetcoinDeveloperClient } from "@netcoin/developer";

const nc = new NetcoinDeveloperClient("https://api.netcoin.online", {
  developerId: "my-game-studio",
});

// Cap what a leaked API key can do before anything else.
await nc.setFundingPolicy({ dailyCapSats: 5_000_000, paused: false });

// Reward a player for completing a daily quest (idempotent on retry).
const reward = await nc.sendReward({
  playerId: "player-42",
  address: "net1q...",
  amountSats: 2_500,
  reason: "daily_quest",
  idempotencyKey: "daily-quest-player-42-2026-07-15",
});
console.log(reward.payout_plan); // unsigned — sign and broadcast yourself

// Create a payment link a customer can pay at pay.netcoin.online.
const link = await nc.createPaymentLink({ address: "net1q...", amount: "5.00", title: "Starter pack" });
console.log(link.checkout_url);
```

## Webhook signature verification

```js
import { verifyNetcoinWebhook } from "@netcoin/developer";

const ok = await verifyNetcoinWebhook(rawRequestBody, req.headers["x-netcoin-signature"], webhookSecret);
```

`verifyNetcoinWebhook` uses `node:crypto` and is meant for a developer's own
backend receiving deliveries — verify signatures server-side, not in a browser.

## Endpoint coverage

| Method | `NetcoinDeveloperClient` | Endpoint |
|---|---|---|
| `sendReward` | `POST /api/developer/rewards` |
| `sendBatchRewards` | `POST /api/developer/rewards/batch` |
| `listRewards` | `GET /api/developer/rewards` |
| `requestWithdrawal` | `POST /api/developer/withdrawals` |
| `listWithdrawals` | `GET /api/developer/withdrawals` |
| `getFundingPolicy` / `setFundingPolicy` | `GET`/`POST /api/developer/funding-policy` |
| `createPaymentLink` | `POST /api/developer/payment-links` |
| `watchAddress` | `POST /api/developer/watch-addresses` |
| `listDeposits` | `GET /api/developer/deposits` |
| `registerWebhook` | `POST /api/developer/webhooks` |
| `queueWebhookEvent` | `POST /api/developer/webhook-events` |
| `deliverWebhookEvents` | `POST /api/developer/webhook-events/deliver` |
| `getWebhookVerifiers` | `GET /api/developer/webhook-verifiers` |
| `buildUnsignedTransaction` | `POST /api/developer/transactions/build` |
| `simulateRewards` | `POST /api/developer/simulate/rewards` |
| `getDashboard` / `getConsole` | `GET /api/developer/dashboard` / `/console` |
