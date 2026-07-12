# M2 — Trust Realization Plan

## Goal

Move from source-complete trust scaffolding to real device, signing, reproducibility, fuzz, and audit evidence.

## Sprint order

### Sprint M2-A — Production PSBT/offline signing UX

Build a complete user flow:

```text
create unsigned PSBT
export PSBT
offline signer imports PSBT
sign
export signed PSBT
wallet imports signed PSBT
validate signatures
broadcast
record transcript
```

Acceptance:

- Works without hardware device.
- Malformed PSBTs rejected.
- Transcript file created.
- Broadcast path refuses unsigned/incomplete payloads.

### Sprint M2-B — Ledger Nano S Plus physical signing

Acceptance:

- Device detected through WebUSB/WebHID.
- Address confirmation transcript captured.
- Transaction signing transcript captured.
- User verifies signed transaction broadcasts or dry-run validates.
- Evidence file produced.

### Sprint M2-C — Trezor path

Acceptance:

- Same transcript format as Ledger.
- If no device available, status remains `deferred`, not `complete`.

### Sprint M2-D — Release security

Acceptance:

- Independent reproducible build on second machine.
- Release signing key ceremony recorded.
- SBOM and SLSA provenance generated and validated.

### Sprint M2-E — Fuzz and audit prep

Acceptance:

- 100M+ fuzz evidence file.
- Audit firm call notes collected.
- Scope packet ready.

## Evidence files

```text
reports/m2_evidence/hardware_wallet_device_evidence.json
reports/m2_evidence/independent_repro_build.json
reports/m2_evidence/release_signing_key_ceremony.json
reports/m2_evidence/fuzz_100m_report.json
reports/m2_evidence/audit_scoping_notes.json
```

## Exit criteria

`make m2-rc-strict` passes with real evidence.
