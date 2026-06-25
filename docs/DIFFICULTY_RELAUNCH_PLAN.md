# Real Difficulty / Testnet Relaunch Plan

> **Status (2026-06-22): DECIDED + BUILT on the `testnet-v2` branch, NOT yet
> deployed.** Decisions: 2-minute blocks (`TARGET_SPACING_SECONDS=120`), retarget
> every 30 blocks, easy launch at the PoW floor with the fast retarget ramping up,
> and the testnet lone-miner min-difficulty rule (`MIN_DIFFICULTY_GAP_SECONDS`).
> New genesis (`GENESIS_MESSAGE` = "...testnet v2..."). 297 tests pass on the
> branch. **The live seeds remain on v1 until an explicit go** — relaunch = wipe
> seed data + redeploy this branch + re-fund the faucet (runbook below).

Today NetCoin mines at trivial difficulty (`INITIAL_BITS = 0x207FFFFF`, the
easiest possible target). Anyone can mine hundreds of blocks per second, so there
is **no real proof-of-work, no competition, and no meaningful security** — it's a
chain in name only. Making mining "real" (blocks take minutes, finding one costs
actual work) is the single biggest step toward NetCoin being a genuine PoW
network instead of a sandbox.

## Why this needs a relaunch (read first)

Difficulty is **consensus**. The genesis block's `bits` is baked in, and every
block's `bits` is validated against `expected_bits_for_height`, which depends on
`INITIAL_BITS`, `TARGET_SPACING_SECONDS`, and `DIFFICULTY_ADJUSTMENT_INTERVAL`.

Changing any of those re-defines what a valid chain is, so the **existing
height-~429 chain would no longer validate**. There is no in-place migration:
real difficulty means a **fresh genesis and a new testnet** ("testnet v2"). That
resets the chain, the seeds' data, all mined coins, and the faucet balance.

**This is a deliberate decision, not a silent upgrade.** It should ship as a
named event (e.g. the v0.5.0 testnet relaunch).

## Target behavior

- A block should take roughly the **target spacing** for the actual miners on the
  network — not instant, not hours.
- Suggested testnet params (faster feedback than Bitcoin mainnet):
  - `TARGET_SPACING_SECONDS = 120` (2-minute blocks) — quick enough to watch.
  - `DIFFICULTY_ADJUSTMENT_INTERVAL = 30` (retarget every ~hour) so difficulty
    tracks a small, changing miner set quickly instead of after 2016 blocks.
  - `INITIAL_BITS`: a modest target so a single CPU miner takes ~tens of seconds
    at launch; the fast retarget then settles it toward the 2-minute target as
    miners join/leave.
  - Keep `POW_LIMIT_BITS` as the easiest allowed target (difficulty floor).
- **Testnet min-difficulty rule (recommended):** like Bitcoin testnet, allow a
  min-difficulty block if no block has been found in, say, `2 × spacing`. This
  stops a lone miner from getting stuck when the network shrinks. (Small change in
  `expected_bits_for_height`.)

## Code changes

1. `params.py`: set `TARGET_SPACING_SECONDS`, `DIFFICULTY_ADJUSTMENT_INTERVAL`,
   `INITIAL_BITS`; bump a network/genesis identifier (new `GENESIS_MESSAGE` and/or
   `GENESIS_TIMESTAMP`) so the new genesis hash differs from the current one and
   old/new nodes can't cross-talk.
2. `chain.py`: (optional) the testnet min-difficulty-after-2×-spacing rule in
   `expected_bits_for_height`.
3. Tests: difficulty retarget direction (faster blocks → harder), the clamp, and
   the min-difficulty rule. (The retarget math itself already exists and works.)

## Calibration

`INITIAL_BITS` should match expected launch hashpower. Approach: measure the pure-
Python miner's hashes/sec on a typical machine, pick a target where
`expected_seconds ≈ target_spacing / N_miners`, then rely on the (now fast)
retarget to converge. Erring **easy** at launch is safer — the retarget raises
difficulty as miners join; starting too hard could stall genesis mining.

## Relaunch runbook (operational)

1. Land the param changes + tests; cut the release (v0.5.0).
2. **Wipe** each seed's data dir (`/opt/netcoin/.netcoin-testnet`) — old chain is
   incompatible. Back it up first for archival.
3. Redeploy v0.5.0 to all three seeds (existing `deploy_seed.sh` flow), restart;
   they mine the new genesis and the first blocks at real difficulty.
4. Reset the faucet wallet / re-fund it from new coinbase maturity.
5. Announce the relaunch (the chain height resets to 0; testers re-request faucet
   coins; previously mined balances are gone — it's a testnet).

## Decision needed from the maintainer

- Go / no-go on resetting the public testnet.
- Final params: block spacing, retarget interval, launch difficulty, and whether
  to include the min-difficulty rule.

Until then, mining stays trivial. Everything else (wallets, filters, channels,
sighash, taproot) is unaffected by this decision and ships independently.
