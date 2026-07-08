# Professional code upgrade bundle

This repository includes a concrete 15-workstream professionalization manifest at
`config/professional_upgrade_manifest.json`. The manifest is intentionally not a
mainnet claim: it verifies code/docs/config/test anchors and keeps
`production_ready=false` until external audits, hostile testnet evidence, and
operator runbooks prove the system.

Run:

```bash
python tools/professional_upgrade_audit.py --fail-on-issues
```

The largest applied product upgrade in this pass is the Markets Labs engine:
Polymarket-style CLOB snapshots, aggregated price levels, ticker APIs, market / IOC / FOK orders,
portfolio mark views, richer market metadata, and optimistic-resolution fields.
