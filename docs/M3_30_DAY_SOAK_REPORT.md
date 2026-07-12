# M3 30-Day Public Soak Report Template

Operational M3 requires a 30-day unattended public testnet soak.

## Required metrics

- Start and end timestamps
- Independent operator count
- Reachable public node count
- Mining operator count
- Non-founder mined block hash
- Peer diversity by operator and network group
- Block propagation P50/P99
- Orphan rate
- Mempool depth P50/P99
- Incident count and links
- Founder intervention count

## Strict evidence file

```text
reports/m3_evidence/soak_30_day_report.json
```

The strict M3 gate expects `ok: true`, duration at least 30 days, at least 10 independent operators, at least one non-founder mined block, and no hidden incident log.
