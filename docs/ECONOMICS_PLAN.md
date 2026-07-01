# NetCoin economics plan

NetCoin uses a simple deterministic reward schedule:

- **Starting block subsidy:** `50 NET`.
- **Reward interval:** every `265,000` blocks.
- **Reduction size:** each event reduces the current subsidy by **10%**.
- **Formula:** `subsidy = 50 NET × (9/10)^epoch`, where `epoch = floor(height / 265,000)`.
- **First reduction:** height `265,000`, from `50 NET` to `45 NET`.

This is not a Bitcoin-style 50% halving. It is a 10% reward reduction every
265,000 blocks — a gentle, long taper.

## Reward table

| Height range | Subsidy |
|---:|---:|
| `0` - `264,999` | `50 NET` |
| `265,000` - `529,999` | `45 NET` |
| `530,000` - `794,999` | `40.5 NET` |
| `795,000` - `1,059,999` | `36.45 NET` |
| `1,060,000` - `1,324,999` | `32.805 NET` |
| `1,325,000` - `1,589,999` | `29.5245 NET` |

Rewards are tracked in satoshi-style integer units, so very small later rewards
are floored to the nearest atomic unit.

## Supply estimate

Ignoring rounding, the geometric reward schedule approaches roughly:

```text
265,000 blocks × 50 NET / 0.10 = 132,500,000 NET
```

So the long-run minted supply target is approximately **132.5 million NET** before
transaction fees. Fees are not newly minted; they are paid by spenders to miners.

> Note: a 10% reduction decays much more slowly than a 20% one, so the supply
> ceiling (~132.5M) is roughly double what a 20% schedule at the same interval
> would give (~62.5M). `MAX_MONEY` is set to `132_500_000 NET` to match.

## Upgrade activation on the live public testnet

The public testnet previously activated a short random-emission experiment at
height `1,000`. To avoid invalidating already-mined blocks, the deterministic
schedule is activation-gated at height `4,200` in code.

That compatibility rule means:

- Heights below `1,000` keep the original `50 NET` subsidy.
- Heights `1,000` through `4,199` keep the already-active legacy testnet emission
  window so current history remains valid.
- Heights `4,200+` use the new deterministic 10% reward schedule.
- The public reduction events are still based on absolute height, so the first
  reduction is at height `265,000`.

Every public node and miner should update before height `4,200` so they agree on
block rewards after activation. Because no reduction has happened yet (the first
is at height `265,000`) and the chain is still early, changing the interval or
reduction size does not invalidate any existing block.
