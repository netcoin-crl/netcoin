# NetCoin v0.37 Security Hardening, Fuzz, and Audit Prep

v0.37 adds a security/audit-prep manifest and gate around the migration work from v0.33 through v0.36.

Files:

- `architecture/security-fuzz-audit-vectors.json`
- `netcoin/security_hardening.py`
- `tools/run_security_audit_prep.py`

The manifest tracks:

- threat model coverage
- fuzz target inventory
- audit gate inventory
- required release docs
- required operational hardening tools

Run:

```bash
python tools/run_security_audit_prep.py
make v037-check
```

This is audit preparation, not an external audit. Before production or mainnet claims, NetCoin still needs independent cryptography/security review, real hostile-network soak history, and full CI with Rust/Cargo, npm, and Playwright installed.
