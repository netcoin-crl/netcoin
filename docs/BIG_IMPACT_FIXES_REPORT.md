# NetCoin v0.15 Big Impact Fixes

This pass implements the five highest-impact next upgrades identified in the v0.14 thorough feature review.

## 1. Hardware signer adapter layer

Updated `netcoin/signer.py`:

- Added `HardwareTransport` protocol.
- Added `CommandHardwareTransport` for external vendor/HWI-style bridge commands.
- Added `FileHardwareTransport` for QR/file/air-gapped signing workflows.
- Added `SimulatedHardwareTransport` for tests and devnet demos.
- Upgraded `HardwareSigner` from a pure placeholder into a real adapter-driven signer.
- Kept production safety: simulated transports are rejected unless `require_real_device=False`.
- Added `hardware_signer_from_env()` for deployable configuration.

## 2. Hardened P2P header sync planner

Updated `netcoin/sync.py`:

- Added linked-header validation.
- Added checkpoint mismatch detection.
- Added expected-start-height enforcement.
- Added peer chainwork tracking.
- Added bad-peer penalties through `PeerSyncCoordinator`.
- Added peerdb-based assignment.
- Added stalled job retry handling.
- Added block locator helper.

This does not claim the binary P2P layer is fully production-grade, but the sync planner is now stricter and safer.

## 3. Exchange hot/cold custody workflow

Updated `netcoin/exchange.py`:

- Added `custody_accounts` table.
- Added hot/warm/cold custody account policies.
- Added single-withdrawal limits.
- Added minimum approval thresholds.
- Added `withdrawal_approvals` table.
- Added withdrawal approval policy evaluation.
- Added hot withdrawal batch preparation.
- Added cold-to-hot transfer accounting.
- Added custody status and hot-wallet coverage report.

## 4. Wallet risk simulator inside send UI

Updated `sites/wallet/index.html` and `sites/wallet/wallet-app.js`:

- Added risk simulator panel directly inside the send confirmation card.
- Shows decision, balance after send, change, inputs, vbytes estimate, and fee rate.
- Warns about high fee rate, dust change, too many UTXOs, wallet-draining sends, and consolidation sends.
- Blocks sends when the simulator detects insufficient selected/available coins.

## 5. Faucet proof-of-work and reputation layer

Added `netcoin/faucet_abuse.py` and updated faucet server/site:

- Proof-of-work challenge issuance and verification.
- Browser challenge solving for low-difficulty faucet protection.
- Reputation scoring from recent abuse events and repeated address requests.
- Daily faucet spend cap calculation.
- Device hint support.
- Abuse summary on faucet status.
- Public `/challenge` endpoint.

## Rating movement

Approximate feature movement after this pass:

| Feature | Before | After |
|---|---:|---:|
| Hardware signer | 3.0 | 6.0 |
| Headers sync | 6.0 | 7.0 |
| P2P hardening | 6.0 | 6.5 |
| Production custody | 4.5 | 6.2 |
| Wallet transaction simulator | 7.0 | 7.8 |
| Faucet hardening | 6.5 | 7.5 |

## Validation

The new regression tests live in:

```text
tests/test_do_it_big_impact_fixes.py
```

Validated with:

```text
python -m compileall -q netcoin tools
python tools/professional_upgrade_audit.py --fail-on-issues
python tools/check_openapi_contract.py
make test-fast
make site-audit
node --check sites/faucet/faucet.js
node --check sites/wallet/wallet-app.js
python -m pytest -q tests/test_do_it_big_impact_fixes.py tests/test_thorough_rerate_fixes.py tests/test_upgrade_layer_plus.py
```

## Remaining production caveat

These upgrades improve readiness, but NetCoin still needs external security review, long-running hostile public testnet evidence, native hardware-device integrations, deeper binary P2P soak testing, and real custody operations before production/mainnet claims.
