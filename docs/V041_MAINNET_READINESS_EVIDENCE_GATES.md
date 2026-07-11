# v0.41 Mainnet Readiness Evidence Gates

v0.41 turns the remaining production blockers into explicit, executable gates.
It implements the code paths and validators for the hard items, but it does not
pretend that source code can replace real-world proof.

## Gates

- Real hardware wallet device testing
- Real Turnstile/hCaptcha backend integration
- Production custody ledger/reserve/cold-signing evidence
- External crypto/security audit package and evidence validation
- Public P2P soak evidence
- Long-running Python suite confidence
- Mainnet launch checklist approval
- Public testnet incident/runbook history

## Source checks

```bash
python3 tools/check_mainnet_readiness_gates.py
python3 tools/run_mainnet_readiness.py --out reports/mainnet_readiness_source_report.json
```

Source mode proves the code paths, manifests, schemas, custody smoke checks, and
runner wiring exist.

## Strict checks

```bash
python3 tools/run_mainnet_readiness.py --strict --timeout 300 --out reports/mainnet_readiness_report.json
```

Strict mode requires evidence files in `reports/mainnet_evidence/` or live
provider/network configuration. Until those artifacts exist, production/mainnet
claims remain blocked.

## Evidence hash format

For evidence JSON files, compute `evidence_hash` as the SHA-256 of the canonical
JSON body excluding the `evidence_hash` field. The helper
`netcoin.mainnet_readiness.stable_hash_json()` implements the canonical hash.

## Honesty boundary

The project may be source-complete and strict-testnet-proven before these gates
pass, but it is not mainnet/production-ready until all v0.41 strict gates return
`ok: true`.
