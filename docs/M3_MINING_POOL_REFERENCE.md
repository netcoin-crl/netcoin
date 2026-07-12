# M3 Mining Pool Reference

M3 needs at least one non-founder miner. This reference describes a minimal Stratum-lite pool without changing consensus.

## Components

- Pool coordinator: tracks current tip, builds candidate work, validates submitted shares.
- Miner worker: polls pool job endpoint, searches nonce space, submits candidate blocks.
- Payout ledger: testnet-only accounting for contributed shares.

## Minimal API sketch

```text
GET  /pool/job
POST /pool/submit-share
POST /pool/submit-block
GET  /pool/miners
```

## Required evidence

Operational M3 needs a non-founder mined block hash and pool/operator logs proving it was not mined by founder infrastructure.

This document is source-level reference only; no mainnet mining-pool claim is made.
