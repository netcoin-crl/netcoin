# Hardware Wallet Integration Runbook

NetCoin M2 supports a source-level hardware-wallet contract for Ledger and
Trezor style devices. The contract is PSBT-first: the browser or CLI prepares
a `netpsbt:` payload; the device reviews and signs it; the wallet imports the
signed PSBT and broadcasts the finalized transaction.

## Supported source transports

- `webhid` for browser Ledger/Trezor integrations.
- `webusb` where the device/browser combination supports it.
- `file-psbt` for offline desktop transfer.
- `qr-airgap` for future animated-QR flows.

## Device evidence required before operational completion

Strict evidence must live outside source secrets at
`reports/m2_evidence/hardware_wallet_device_evidence.json` and include:

- device family and model,
- firmware version,
- transport,
- derivation path,
- PSBT hash,
- device-displayed address review,
- device-displayed transaction review,
- fee review,
- change-output review,
- signed PSBT,
- operator attestation,
- evidence hash.

## Physical test recommendation

Use the Ledger Nano S Plus first, because it is already on the project shopping
list. Then repeat the transcript with one Trezor model. Do not claim hardware
wallet support complete until both transcript families pass.

physical-device evidence marker for strict M2.
