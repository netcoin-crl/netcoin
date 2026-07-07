# NetCoin Exchange Readiness

NetCoin is educational/testnet software. Exchange-style integrations should remain private/testnet until security, liquidity, compliance, and operational requirements are met.

## Required Policies

- deposit confirmation count
- reorg handling and credit rollback
- withdrawal batching and review queue
- hot/cold wallet separation
- address validation endpoint
- chain halt/fork alerting
- proof-of-reserves guide
- release verification process

## Reorg Handling

- Do not credit deposits until the configured confirmation threshold is reached.
- Track block hash at credit time.
- On reorg, recalculate deposit status from canonical chain.
- Freeze withdrawals when a deep reorg or chain split is detected.

## Operational Checks

- Monitor node height, tip hash, peers, mempool size, and seed divergence.
- Keep at least two independently hosted nodes.
- Verify releases before upgrading exchange infrastructure.
- Maintain wallet backups and restore drills.
