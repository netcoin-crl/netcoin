# M5 Post-Launch Monitoring

Status: **source-ready, evidence required**.

The first 30 days after genesis require active monitoring and public incident discipline.

## Required dashboards

- block height,
- peer count,
- independent node count,
- miner diversity,
- mempool depth,
- orphan/reorg count,
- explorer/API health,
- faucet disabled or clearly testnet-only,
- public incident log.

## T+1 day checks

- 100+ blocks observed.
- 5+ independent miners observed.
- No emergency hard fork.
- No unreconciled chain split.

## T+7 day checks

- Independent operator confirms chain state.
- Public state hash recorded.
- All major incidents disclosed.

## T+30 day checks

- No unplanned hard fork required.
- Public retrospective written.
- Any launch debt converted into tracked issues.

Evidence files:

- `reports/m5_evidence/first_100_blocks.json`
- `reports/m5_evidence/five_independent_miners.json`
- `reports/m5_evidence/t_plus_7_state_confirmation.json`
- `reports/m5_evidence/t_plus_30_stability.json`
