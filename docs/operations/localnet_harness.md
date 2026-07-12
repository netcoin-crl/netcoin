# Localnet Harness

Wave 1.1 adds a repeatable multi-node localhost network for validating relay,
sync, PEX, compact blocks, fork choice, restart replay, and process cleanup
before a build reaches the public testnet.

Run the harness directly:

```bash
python tools/run_localnet.py --nodes 3 --json
```

Run the pytest lane:

```bash
python -m pytest -m localnet -q
```

The harness starts real `python -m netcoin node` subprocesses with SQLite
storage, distinct data directories, dynamically allocated HTTP and binary-P2P
ports, localhost-only binding, and rate limiting disabled for deterministic test
traffic. Ports are reserved as a collision-free set before startup.

Assertions covered:

- every node starts and serves `/health`;
- line-topology peer gossip propagates across the network via `/peers`;
- node 0 mines mature funding blocks and all nodes converge through headers-first sync;
- a signed transaction enters node 0 and relays to every node's mempool;
- a mined block containing the transaction relays to every node;
- compact-block and missing-transaction endpoints return reconstructable data;
- a hard-killed node restarts from the same data directory and resyncs;
- a contested fork resolves to the higher-work chain after partitions reconnect;
- every child process is terminated during teardown.

Use `--keep-artifacts --root-dir <path>` when debugging. Each node writes
`node-N.stdout.log`, `node-N.stderr.log`, and its own `node-N/` chain directory.

The full localnet lane is intentionally separate from the default fast suite
because it mines real blocks and spawns OS processes.
