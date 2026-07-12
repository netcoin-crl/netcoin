# Mainnet performance targets

M4 cannot be considered operationally mainnet-ready until benchmark evidence
shows nodes can handle expected load.

## Targets

- Block validation P95: < 500 ms at expected block size.
- Full-node memory: < 200 MB steady-state under normal load.
- Storage growth: < 10 GB/year at expected chain load.
- Peer handshake and sync: documented P50/P95.
- Mempool operations: no unbounded growth under policy limits.

## Required benchmark report

Strict M4 requires:

```text
reports/m4_evidence/performance_benchmark_report.json
```

The report must include hardware profile, commit hash, dataset size, command
lines, raw results, and pass/fail against each target.
