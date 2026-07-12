# Fuzz Accumulator

Wave 1.3 adds repeatable fuzz evidence instead of one-off smoke output.

Run a small local smoke:

```bash
python tools/run_nightly_fuzz_accumulator.py --iterations 100 --allow-missing-cargo
```

The nightly workflow runs:

```bash
python tools/run_nightly_fuzz_accumulator.py --iterations 2000000
```

Outputs:

- `reports/nightly_fuzz_report.json` — top-level run status.
- `reports/fuzz_history/<timestamp>-fuzz.json` — raw fuzz report from
  `python -X dev -m netcoin fuzz`.
- `reports/fuzz_history/<timestamp>-rust-consensus-parity.json` — Python vs
  Rust consensus parity report.
- `reports/fuzz_history_summary.json` — accumulated real fuzz cases.

The accumulator only counts reports whose JSON has `ok: true`. It does not
claim the 100M fuzz target until `total_cases >= goal_cases`, and it does not
claim Rust executable differential coverage when the parity report ran in
source-only mode.
