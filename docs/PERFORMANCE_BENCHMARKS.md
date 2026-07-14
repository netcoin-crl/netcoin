# Performance Benchmarks

P2 adds a source-level performance benchmark for audit-readiness evidence. It is
intended to catch large regressions in block validation, restart replay, memory,
and mempool admission before they reach public testnet nodes.

Run locally:

```bash
python tools/run_perf_benchmark.py --out reports/perf/perf_benchmark_report.json
```

Or through Make:

```bash
make perf-benchmark-check
```

The JSON report schema is `netcoin-perf-benchmark-v1`.

## Metrics

The benchmark records:

- block-validation latency while adding mined blocks into a fresh chain:
  `p50_ms`, `p99_ms`, `max_ms`, `mean_ms`;
- restart replay time by reopening a persisted chain directory;
- peak process RSS as `max_rss_mb`;
- mempool admission throughput as `transactions_per_second`.

Default CI thresholds are intentionally conservative and live in
`tools/run_perf_benchmark.py`. Override them with:

```bash
python tools/run_perf_benchmark.py --thresholds perf-thresholds.json
```

## CI Evidence

`.github/workflows/perf-benchmark.yml` runs the benchmark and uploads:

```text
reports/perf/perf_benchmark_report.json
```

The report is source-level benchmark evidence. It does not claim public seed
performance, hardware-isolated benchmarking, or mainnet capacity certification.
