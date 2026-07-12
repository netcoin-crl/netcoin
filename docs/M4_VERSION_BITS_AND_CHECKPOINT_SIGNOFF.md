# M4 consensus signoff: version bits and early checkpointing

This document is a blocker record, not an implementation.

M4 needs a version-bits soft-fork path and an early-mainnet checkpoint policy,
but both touch consensus or launch-critical governance. They must not be added
quietly as ordinary code changes.

## Required before implementation

- Accepted NIP describing version-bits fields, thresholds, windows, timeout, and fallback.
- Accepted NIP describing checkpoint purpose, expiration, and removal criteria.
- Explicit same-session user signoff before consensus code changes.
- Python/Rust/TypeScript implementation plan.
- New parity vectors.
- Testnet activation rehearsal evidence.

## Evidence path

Strict M4 requires:

```text
reports/m4_evidence/consensus_change_signoff.json
```

Until that exists, the correct status is:

```text
blocked-by-consensus-signoff
```

M4 blocker marker: explicit same-session user signoff is required before any consensus implementation.
