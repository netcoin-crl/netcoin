# Mainnet genesis distribution proposal — draft only

This is a draft structure for discussion. It is **not** an approved genesis
allocation and must not be represented as final.

## Recommended initial policy range

- Team: 10–20%, four-year vesting with one-year cliff.
- Treasury: 5–15%, multisig controlled with public spend reporting.
- Community/testing/grants: 5–20%, including testnet pilot and node-operator incentives.
- Miner emission: the remaining economic weight through the published emission curve.

## Draft JSON source

The editable draft lives at:

```text
config/mainnet_distribution.example.json
```

## Approval rules

Before mainnet launch, the final distribution must include:

- total supply model,
- max supply or asymptotic emission statement,
- every premine or allocation bucket,
- vesting enforcement method,
- multisig signer list or governance process,
- snapshot/airdrop eligibility if any,
- public review period,
- signed approval hash.

## Evidence path

Strict M4 requires:

```text
reports/m4_evidence/genesis_distribution_approval.json
```

Do not generate or launch a real mainnet genesis from this draft until a NIP and
public approval process are complete.

M4 blocker marker: this is not an approved genesis allocation.
