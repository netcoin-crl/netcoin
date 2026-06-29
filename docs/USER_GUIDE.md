# NetCoin User Guide

This guide is for the current testnet/demo NetCoin app stack.

## Wallet basics

Use the browser wallet to:

- create or unlock a wallet profile
- copy your receive address
- show a QR code/payment link
- save contacts
- send NetCoin
- review transaction labels and notes
- export contacts/backups

Always back up your wallet before sending funds.

## Payments and invoices

NetCoin supports app-layer invoices and checkout pages.

A merchant or user can create an invoice with:

```text
recipient address
amount
memo
expiration
confirmation requirement
```

The checkout page shows a payment URI and status. Statuses include unpaid, pending, confirmed, underpaid, overpaid, and expired.

## Public pages

The app layer can serve:

```text
/pay/<invoice_id>       checkout page
/receipt/<txid>         receipt page
/receipt/<txid>.pdf     receipt PDF
/u/<username>           public profile
/tip/<username>         tip page
/donate/<username>      donation page
/gift/<claim_code>      gift claim page
```

## Community tools

Testnet/demo tools include:

- gifts
- airdrop payout plans
- bounties
- community rewards
- tip buttons
- leaderboards

Payouts are planned first, then reviewed and manually signed by an operator.

## Phase 7 tools

Phase 7 app-layer tools include:

- recurring payment agreements
- 2-of-3 escrow records
- signed-message polls
- testnet/play-money prediction markets
- simple contract templates

These are app-layer/demo features, not Ethereum-style consensus contracts.

## Safety note

Unless the operator explicitly announces otherwise, treat this as testnet/demo software. Do not use it for real-value payments or regulated markets.
