# M5 Genesis Ceremony

Status: **blocked until M4 strict evidence and explicit approval**.

This document defines the ceremony. It does not mine genesis and does not approve launch.

## Preconditions

- M4 strict evidence passes.
- Genesis distribution approval exists.
- Third-party genesis review exists.
- Signed binaries exist.
- At least 10 independent node operators are ready.
- At least 5 independent miners are ready.
- Incident owner and on-call rotation are active.

## Ceremony record

The ceremony record must include:

- exact source commit,
- release tag,
- genesis config hash,
- genesis block hash,
- signer identities,
- independent witness attestations,
- operator confirmation commands,
- halt decision if any mismatch occurs.

Strict evidence files:

- `reports/m5_evidence/genesis_ceremony.json`
- `reports/m5_evidence/independent_witnesses.json`

## Halt rule

If any independent operator sees a different genesis hash, launch halts. Do not patch around a mismatch during ceremony.
