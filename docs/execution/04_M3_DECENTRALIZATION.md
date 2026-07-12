# M3 — Public Decentralization Plan

## Goal

NetCoin stops being a single-operator AWS network and becomes a public testnet with independent operators.

## Workstreams

### M3.1 Operator recruitment

Target:

- 10+ independent nodes.
- 4+ operators minimum.
- At least 2 non-AWS environments.
- At least one home or bare-metal node.

### M3.2 Node installer hardening

- Test Docker Compose path.
- Test systemd path.
- Add uninstall/recover docs.
- Add low-bandwidth mode docs.

### M3.3 DNS seed delegation

- Decide domains.
- Publish DNS seed plan.
- Verify seed rotation.

### M3.4 Live P2P validation

- Prove AddrV2 with public peers.
- Prove PEX behavior.
- Prove compact block relay.
- Measure bandwidth mode.

### M3.5 Mining diversity

- One non-founder mined block.
- Mining pool reference tested.
- Record block hash and miner evidence.

### M3.6 30-day public soak

Track:

- peer diversity,
- propagation P50/P99,
- orphan rate,
- mempool depth,
- incidents,
- restarts,
- chain splits.

## Evidence files

```text
reports/m3_evidence/independent_nodes.json
reports/m3_evidence/dns_seed_delegation.json
reports/m3_evidence/soak_30_day_report.json
reports/m3_evidence/non_founder_mined_block.json
reports/m3_evidence/testnet_soft_fork_rehearsal.json
```

## Exit criteria

`make m3-rc-strict` passes with real evidence.
