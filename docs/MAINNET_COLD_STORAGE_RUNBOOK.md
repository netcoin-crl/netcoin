# Mainnet cold-storage multisig runbook

This runbook defines the source-side process for team, treasury, and operational
allocations. It does not contain private keys or signer identities that should
remain private.

## Required ceremony

1. Select signer set and threshold.
2. Generate keys on separate devices.
3. Verify addresses independently.
4. Record public xpub/address fingerprints.
5. Sign ceremony transcript.
6. Test small-value spend on testnet.
7. Store backup envelopes in separate locations.
8. Publish public treasury address and spend policy.

## Required controls

- No single signer can move funds.
- Treasury and team allocations are separate.
- Emergency spend requires documented incident reference.
- Every spend has a public memo and transaction id.

## Evidence path

Strict M4 requires:

```text
reports/m4_evidence/cold_storage_ceremony.json
```
