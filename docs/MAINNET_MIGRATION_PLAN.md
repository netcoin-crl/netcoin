# Mainnet migration plan

M4 requires a clear path from public testnet usage to mainnet without surprising
users.

## Principles

- Testnet coins are not real-money claims unless a public conversion policy says so.
- Any 1:1 airdrop must use a published snapshot date and reproducible script.
- Users should not be forced to expose seed phrases.
- Existing testnet keys may be eligible by signing messages, not by sharing secrets.
- The final snapshot must be independently reproducible.

## Required mainnet migration artifacts

- Snapshot height/date.
- Snapshot script hash.
- Eligibility policy.
- Dispute window.
- Anti-sybil rules.
- Airdrop or no-airdrop decision.
- Wallet instructions.
- Final migration announcement.

## Evidence path

Strict M4 requires migration approval as part of:

```text
reports/m4_evidence/genesis_distribution_approval.json
```
