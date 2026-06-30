# NetCoin economics plan

NetCoin now uses a simple deterministic reward schedule:

- **Starting block subsidy:** `50 NET`.
- **Reward interval:** every `210,000` blocks.
- **Reduction size:** each event reduces the current subsidy by **20%**.
- **Formula:** `subsidy = 50 NET × (4/5)^epoch`, where `epoch = floor(height / 210,000)`.
- **First reduction:** height `210,000`, from `50 NET` to `40 NET`.

This is not a Bitcoin-style 50% halving. It is a 20% reward reduction every
210,000 blocks.

## Reward table

| Height range | Subsidy |
|---:|---:|
| `0` - `209,999` | `50 NET` |
| `210,000` - `419,999` | `40 NET` |
| `420,000` - `629,999` | `32 NET` |
| `630,000` - `839,999` | `25.6 NET` |
| `840,000` - `1,049,999` | `20.48 NET` |
| `1,050,000` - `1,259,999` | `16.384 NET` |
| `1,260,000` - `1,469,999` | `13.1072 NET` |

Rewards are tracked in satoshi-style integer units, so very small later rewards
are floored to the nearest atomic unit.

## Supply estimate

Ignoring rounding, the geometric reward schedule approaches roughly:

```text
210,000 blocks × 50 NET / 0.20 = 52,500,000 NET
```

So the long-run minted supply target is approximately **52.5 million NET** before
transaction fees. Fees are not newly minted; they are paid by spenders to miners.

## Upgrade activation on the live public testnet

The public testnet previously activated a short random-emission experiment at
height `1,000`. To avoid invalidating already-mined blocks, the deterministic
20% schedule is activation-gated at height `4,200` in code.

That compatibility rule means:

- Heights below `1,000` keep the original `50 NET` subsidy.
- Heights `1,000` through `4,199` keep the already-active legacy testnet emission
  window so current history remains valid.
- Heights `4,200+` use the new deterministic 20% reward schedule.
- The public reduction events are still based on absolute height, so the first
  reduction remains height `210,000`.

Every public node and miner should update before height `4,200` so they agree on
block rewards after activation.
