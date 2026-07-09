# NetCoin v0.33 Hostile P2P / Network Soak Tests

v0.33 adds deterministic hostile-network soak gates. The scenarios live in `architecture/hostile-p2p-soak-scenarios.json` and are executed by `tools/run_p2p_soak.py`.

Covered conditions:

- invalid header spam
- duplicate header spam
- checkpoint-poisoning attempts
- partition heal / reorg-resilience smoke behavior
- eclipse-attempt detection
- peer ban-score escalation

The gate is intentionally deterministic so the Python reference can be ported to Rust/node tests without ambiguity.

Run:

```bash
python tools/run_p2p_soak.py
make v033-check
```
