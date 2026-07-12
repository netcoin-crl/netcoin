# Chaos Drill

Wave 1.4 adds a local-only chaos drill for exercising the incident runbook
against real NetCoin node subprocesses.

Run a drill:

```bash
python tools/run_chaos_drill.py --nodes 3 --json
```

Run the pytest lane:

```bash
python -m pytest tests/test_wave1_4_chaos_drill.py -m localnet -q
```

The drill is intentionally local-only. It starts nodes through
`tools/run_localnet.py`, binds them to `127.0.0.1`, uses temporary data
directories, and refuses non-local node URLs. It does not SSH, deploy, restart
systemd services, or touch public seeds.

Drills covered:

- kill a node during catch-up, restart it, and assert resync;
- corrupt a non-consensus mempool sidecar file and assert node startup/sync;
- inject a dead local peer and assert relay/sync recovery continues;
- partition nodes, mine competing tips, reconnect, and assert convergence.

Use `--keep-artifacts --root-dir <path>` to preserve node logs and data dirs for
debugging. The report is structured JSON and states what it does not claim.
