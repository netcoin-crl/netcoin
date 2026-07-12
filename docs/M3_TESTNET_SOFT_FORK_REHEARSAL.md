# M3 Testnet Soft-Fork Rehearsal Plan

This is a plan, not activated consensus code.

Consensus/version-bits changes require explicit same-session signoff and a NIP. Do not implement activation logic without that approval.

## Goal

Prove the network can coordinate a planned testnet upgrade before mainnet.

## Source-complete M3 scope

- Document activation phases.
- Define required miner signaling evidence.
- Define rollback/no-activation communication path.
- Require independent operator participation.

## Future implementation scope

- Version-bit deployment parameters.
- Miner signaling in block headers.
- Threshold accounting.
- Lock-in/active transitions.
- Reorg and non-upgraded-node behavior.

## Strict evidence file

```text
reports/m3_evidence/testnet_soft_fork_rehearsal.json
```

It must be based on a real testnet rehearsal after explicit consensus signoff.
