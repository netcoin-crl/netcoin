# NetCoin Post-M5 Engineering Backlog

This document tracks the remaining engineering that turns source-complete
milestone packages into real operational capability.

## Claim policy

Safe claim:

> The post-M5 backlog has source-level contracts, validators, and release gates.

Unsafe claim:

> Hardware wallets, mainnet genesis, liquidity, and ecosystem utility are fully
> operational.

Real external evidence is still required for physical devices, public network
operators, consensus activation, genesis approval, listings, and utility usage.

## 1. Production PSBT/offline signing UX

Delivered source pieces:

- `netcoin/offline_signing.py`
- `config/psbt_offline_workflow.example.json`
- source tests and post-M5 gate coverage

Expected real user flow:

1. Online wallet creates an unsigned `netpsbt:` payload.
2. User exports the PSBT as file/text/QR-ready payload.
3. Offline signer or hardware wallet signs it.
4. User imports the signed PSBT back into the online wallet.
5. Wallet verifies it matches the original unsigned skeleton.
6. Wallet prepares a broadcast package for explicit user approval.

No private keys are included in the export/import/broadcast packages.

## 2. Real hardware wallet integration

Delivered source pieces:

- `netcoin/hardware_bridge.py`
- Ledger/Trezor WebUSB/WebHID transport policy
- physical transcript contract
- source tests and post-M5 gate coverage

Operational completion requires a real transcript from a physical Ledger and/or
Trezor device. Do not fake this file.

## 3. Public P2P hardening

Delivered source pieces:

- `netcoin/p2p_public_hardening.py`
- DNS seed/operator manifest validation
- compact-block, PEX, AddrV2, and home-bandwidth gate checks

Operational completion requires independent operators and real DNS seed
delegation evidence.

## 4. Consensus-upgrade machinery

Delivered source pieces:

- `netcoin/versionbits.py`
- `config/versionbits_rehearsal.example.json`

This is a rehearsal model only. It is intentionally not wired into consensus.
Real activation requires a NIP, parity vectors, Python/Rust/TS implementations,
and explicit signoff.

## 5. Mainnet genesis tooling

Delivered source pieces:

- `netcoin/genesis_manifest.py`
- `config/genesis_manifest.example.json`

This validates draft manifests only. It does not generate, mine, or activate a
mainnet genesis block. Real use requires NIP/governance/legal approval.

## 6. M6 liquidity/market code

Delivered source pieces:

- `netcoin/liquidity.py`
- `config/liquidity_metadata.example.json`

This validates supply/listing metadata and creates CoinGecko-style data. Real
liquidity requires venues, market maker evidence, and public circulating supply
proof.

## 7. M7 utility/ecosystem code

Delivered source pieces:

- `netcoin/ecosystem.py`
- `config/ecosystem_utility.example.json`

Current recommended focus remains `dev-first-bitcoin-family-sandbox` until data
proves a stronger utility path.

## Next operational evidence files

```text
reports/post_m5_evidence/ledger_physical_transcript.json
reports/post_m5_evidence/trezor_physical_transcript.json
reports/post_m5_evidence/public_p2p_independent_operator_set.json
reports/post_m5_evidence/versionbits_nip_signoff.json
reports/post_m5_evidence/genesis_nip_approval.json
reports/post_m5_evidence/liquidity_venue_evidence.json
reports/post_m5_evidence/ecosystem_usage_report.json
```
