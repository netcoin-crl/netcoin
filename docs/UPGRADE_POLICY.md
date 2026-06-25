# Upgrade & Chain-Continuity Policy

The goal: **people never lose their NET because of a software update.** This is a
policy, not a hope — it follows from how the chain works, plus one migration tool
for the rare case a reset is unavoidable.

## The core fact

Balances live in the **chain** (the UTXO set), not in the node program. Updating
the software does not touch balances. The *only* thing that resets balances is
starting a **new chain** (a new genesis). So:

- **Software update** (new node version, same chain) → balances always survive.
- **New genesis / chain reset** → balances reset, *unless* you carry them forward
  with a snapshot allocation (below).

## Versioning rules (SemVer)

- **PATCH / MINOR** (`x.y.z`): features, fixes, and **additive** consensus changes
  only — must keep the existing chain valid. **Never reset the chain.** Existing
  signatures and data must still validate. (Example: SIGHASH types and Taproot
  script-path shipped this way — `ALL`/key-path stayed byte-identical, so v0.4 →
  v0.5 kept every coin.)
- **MAJOR** (`x.0.0`) or an explicit **relaunch**: the only releases allowed to
  change the genesis or break consensus — and even then, **only with a snapshot
  allocation** so balances carry over (unless the old chain has no value and a
  clean reset is intended, as with the one-time testnet v2 PoW relaunch).

A change is "additive" if the current chain still passes `assert_valid_chain`
under the new code. If it doesn't, it's a hard fork → MAJOR + migration.

## Carrying balances across a relaunch (snapshot allocation)

When a new genesis is truly required, no one has to lose coins:

1. **Snapshot** the old chain's balances:
   ```bash
   python -m netcoin --data <old-data-dir> export-allocation --out allocation.json
   ```
   This writes `{address: sats}` for every holder (built from the UTXO set).

2. **Bake the allocation into the new genesis.** Every node starts the new chain
   with the same allocation, so the genesis is deterministic and identical for all:
   ```python
   from netcoin.chain import Blockchain
   from netcoin.migration import load_allocation
   Blockchain("new-data", genesis_allocation=load_allocation("allocation.json"))
   ```
   (For a release, commit the allocation file and load it by default so every
   node agrees.)

3. **Result:** every address keeps its exact balance on the new chain — same keys,
   same address, same coins. Allocated coins sit in the genesis coinbase, so they
   follow the normal coinbase-maturity rule (spendable after `COINBASE_MATURITY`
   blocks on the new chain).

Keys and addresses survive **everything** — the wallet file isn't tied to the
chain, so a holder's identity never changes; at most a balance is re-seeded.

## Relaunch runbook (only for a deliberate MAJOR/relaunch)

1. Decide it's truly necessary (consensus change that can't be additive).
2. `export-allocation` from a seed → `allocation.json`; commit it.
3. Wipe seed data, deploy the new version (which loads the allocation into genesis).
4. Verify the new genesis hash matches across all seeds and balances are present.
5. Announce; testers keep their coins automatically.

## Commitment

From testnet v2 onward, NetCoin commits to **additive-only** consensus changes.
Any future hard fork will ship with a snapshot allocation. "We updated → you kept
your NET" is true by design, and the `export-allocation` tooling makes the
exception safe.
