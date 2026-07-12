# Mainnet monetary policy publication checklist

NetCoin's current testnet emission policy is documented as:

```text
50 NET × 0.9^floor(height / 265000)
```

Mainnet monetary policy must be public, frozen, and reviewed before launch.

## Required publication fields

- Initial subsidy.
- Decay/halving cadence.
- Maximum or asymptotic supply explanation.
- Fee policy.
- Genesis allocation policy.
- Treasury/team/community allocations.
- Vesting and lockup rules.
- Change process for monetary-policy NIPs.

## Rule

No hidden premine, undisclosed allocation, or post-launch monetary-policy change
is acceptable. Any code change to emission or genesis economics requires a public
NIP and explicit signoff.

M4 blocker marker: monetary policy changes require a public NIP.
