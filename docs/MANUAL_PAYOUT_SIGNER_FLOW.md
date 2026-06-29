# Manual Payout Signer Flow

NetCoin app-layer features can create payout plans for refunds, airdrops, gifts, bounties, community rewards, escrow resolutions, prediction-market demo resolutions, and team-wallet proposals.

A payout plan is not automatically broadcast. It is an operator-reviewed signing instruction.

## Why manual signing first

Manual signing avoids putting a hot wallet on the public server before the project has completed a full custody, key-management, and security review.

## Payout statuses

```text
pending_operator_review   created and waiting for approval
ready_for_wallet_signing  approved and ready to export
signed_ready_to_broadcast signed by wallet/operator, not yet recorded as broadcast
broadcast_recorded        txid recorded by operator
rejected                  rejected by operator
```

## Signer bundle contents

The signer bundle contains:

```text
bundle_version
network
payout_plan
operator_checklist
wallet_import.outputs
wallet_import.memo
wallet_import.total
```

The signer should verify every output before signing.

## Safe manual process

1. Open the admin dashboard.
2. Review a pending payout plan.
3. Click **Approve** only if the source record and output list are correct.
4. Export the signer bundle.
5. Move the bundle to a trusted signing wallet.
6. Build and sign the transaction.
7. Broadcast through a trusted NetCoin node.
8. Copy the final txid back into the dashboard.
9. Keep a copy of the bundle and signed transaction artifact for audit records.

## Hot-wallet warning

The code includes custody/signing-policy metadata, but the recommended v1 policy is:

```text
mode=manual_wallet_signing
hot_wallet_enabled=false
require_operator_review=true
max_auto_broadcast_sats=0
```

Do not enable hot-wallet auto-broadcast until you have a separate key-management design, withdrawal limits, monitoring, backups, incident response plan, and audit.
