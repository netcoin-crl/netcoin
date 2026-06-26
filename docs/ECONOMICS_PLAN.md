# NetCoin Economics — Random Emission (NRE)

NetCoin replaces Bitcoin-style halvings with a **yearly random "cut."** Emission
stays gentle and unpredictable instead of stepping down on a fixed schedule, while
remaining fair (no single actor can grind the outcome) and additive (the existing
chain is never reset).

Status: **specified + implemented behind a future activation gate.** The activation
height is pending Codex ratification before any live activation (see
[UPGRADE_POLICY.md](UPGRADE_POLICY.md)). Implementation: `netcoin/emission.py`,
wired into `Blockchain.subsidy`; tests in `tests/test_emission.py`.

## The rule

Emission is divided into fixed-length **emission years** of
`EMISSION_YEAR_BLOCKS = 262_800` blocks (2-minute blocks × ~365 days), indexed
`k = 0, 1, 2, …` starting at `EMISSION_ACTIVATION_HEIGHT` (`A`). Year `k` spans
heights `[A + k·Y, A + (k+1)·Y)`.

- **Year 0** pays a flat `EMISSION_BASE_SUBSIDY = 15 NET` per block (no prior year
  to sample yet).
- **Each year `k ≥ 1`** makes a **cut decision**:
  1. **Delayed seed.** Aggregate the hashes of the first `EMISSION_SEED_BLOCKS = 10`
     blocks of year `k` into a SHA-256 seed. Using blocks from the *start of the new
     year* (rather than the last block of the old one) removes any last actor's
     ability to grind the result.
  2. **Sample.** Use the seed to deterministically draw `EMISSION_SAMPLE_SIZE = 100`
     blocks (with replacement) from year `k−1`.
  3. **Count even hashes.** "Even" = **even hash** (`int(hash, 16) % 2 == 0`), *not*
     even height. PoW hash parity is a genuine ~50/50 coin flip per block; height
     parity is deterministically 50% and carries no randomness.
  4. **Decide.** If at least `EMISSION_EVEN_THRESHOLD = 40` samples are even, the
     reward drops **10%** for year `k` (`reward = reward · 9 / 10`, integer floor).
  5. **Safety.** If no cut has happened for `EMISSION_DRY_YEAR_LIMIT = 3` consecutive
     years, a cut is **forced** regardless of the sample.

### Seed timing (no circular dependency)

The seed for year `k` is only known once year `k`'s first 10 blocks exist, so those
seed-window blocks are paid at the **previous** settled rate (year `k−1`). Year
`k`'s cut applies from block `A + k·Y + 10` onward. A block's subsidy never depends
on its own hash or any later block, so validation is always well defined.

## Why these numbers

### Threshold = 40 (not 50)

The threshold is the real tuning knob, because the sample is ~Binomial(100, 0.5):

| Threshold | P(cut / year) | Character |
|----------:|--------------:|-----------|
| 60 | ~20% | cuts rare → mostly inflationary |
| 50 | ~54% | coin flip → supply is a random walk |
| **40** | **~98%** | **near-certain ~10%/yr disinflation** |

For an **actual financial coin** you want credible, predictable scarcity. Threshold
50 makes total supply a random walk that can drift inflationary for years by chance
— fun for teaching, bad for store-of-value. Threshold 40 behaves like a credible
disinflation schedule while keeping a whisper of randomness, and the 3-dry-year
safety trigger guarantees the reward can never stall. (The 100-block sample size
buys anti-grinding and fairness, **not** supply predictability — that comes from the
threshold.)

### Base subsidy = 15 NET / block → ~40M NET expected supply

Specifying the per-block reward directly sidesteps choosing a supply target.

- Initial annual emission: `15 × 262_800 = 3,942,000 NET/yr`.
- Expected total supply ≈ `initial_annual / d`, where `d = P(cut) × 0.10` is the
  expected annual decay rate (geometric series `Σ (1−d)^k`).
  - Threshold 40 (`d ≈ 0.098`) → **≈ 40M NET** expected total.
  - Threshold 50 (`d ≈ 0.054`) → ≈ 73M NET (for comparison).

### Caveat: expected cap, not a hard cap

~40M is an **expected** total with variance, not a hard ceiling like Bitcoin's 21M.
If a fixed advertised ceiling is ever required, add a deterministic **terminal
floor** (stop cutting / drop to 0 below some minimum reward). Not implemented yet;
the reward currently decays geometrically toward 0.

## Consensus & rollout constraints

- **Additive + activation-gated.** Below `EMISSION_ACTIVATION_HEIGHT` the legacy
  halving subsidy is unchanged, so the current chain stays valid under the new code
  (the definition of additive in [UPGRADE_POLICY.md](UPGRADE_POLICY.md)). No chain
  reset, no snapshot allocation needed.
- **`INITIAL_SUBSIDY` (50 NET) is untouched.** The 15 NET base is the reward *at
  activation* for the new regime only; already-mined blocks keep their original
  subsidy.
- **Activation supersedes halvings.** Past activation, random emission governs and
  the old halving schedule no longer applies (reflected in
  `test_subsidy_halving_schedule`).
- **Activation height = 5_000** (testnet). Chosen against a live tip of ~2,050
  (~4 days of lead at 2-min blocks) so all three seeds can upgrade and re-peer
  first. Because 5_000 < `HALVING_INTERVAL` (210_000), the legacy halving never
  triggers on the live chain — emission supersedes it before the first halving.
  Height-based gating is used because the emission year is defined in blocks.
- **Still open for Codex:** confirm the seeds are upgraded + re-peered before
  height 5,000; decide whether `EMISSION_YEAR_BLOCKS` should be shortened on
  testnet so cuts are observable (with 262_800, the first cut is ~1 year of
  blocks after activation, and one only per year thereafter), while keeping
  262_800 for mainnet.

## Parameters (`netcoin/params.py`)

| Constant | Value | Meaning |
|----------|-------|---------|
| `EMISSION_YEAR_BLOCKS` | 262_800 | blocks per emission year |
| `EMISSION_ACTIVATION_HEIGHT` | 5_000 | first height governed by NRE (testnet; pending Codex seed-upgrade) |
| `EMISSION_BASE_SUBSIDY` | 15 NET | reward at activation |
| `EMISSION_SEED_BLOCKS` | 10 | blocks aggregated for the delayed seed |
| `EMISSION_SAMPLE_SIZE` | 100 | blocks sampled from the prior year |
| `EMISSION_EVEN_THRESHOLD` | 40 | even-hash samples needed to cut |
| `EMISSION_CUT_NUMERATOR` / `_DENOMINATOR` | 9 / 10 | 10% cut |
| `EMISSION_DRY_YEAR_LIMIT` | 3 | consecutive no-cut years that force a cut |
