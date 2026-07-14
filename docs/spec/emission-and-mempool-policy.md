# Emission And Mempool Policy

## Emission Schedule

Emission constants live in `netcoin/params.py`:

- `COIN = 100_000_000`
- `MAX_MONEY`
- `INITIAL_SUBSIDY`
- `REWARD_START_SUBSIDY`
- `REWARD_REDUCTION_INTERVAL`
- `REWARD_REDUCTION_NUMERATOR`
- `REWARD_REDUCTION_DENOMINATOR`
- `REWARD_SCHEDULE_ACTIVATION_HEIGHT`
- legacy NRE compatibility constants

The deterministic public schedule starts at 50 NET and reduces by 10 percent
every 265,000 blocks. The deterministic schedule activates at height 4,200 so
historical public testnet blocks remain valid. A legacy random-emission
compatibility window remains only for historical validation before that height.

The implementation lives in `netcoin/emission.py` and is called through
`Blockchain.subsidy()` in `netcoin/chain.py`.

## Coinbase Reward

`Blockchain.validate_block_against()` computes:

```text
max_reward = subsidy(height, chain_prefix) + fees
```

`Blockchain.validate_coinbase_transaction()` rejects coinbase outputs above that
maximum. Non-genesis coinbase transactions must pay a positive amount.

## Mempool Is Policy

Mempool behavior is policy, not consensus. Blocks may be valid even when a
transaction would not currently be relayed by a public node, as long as the
transaction satisfies block validation rules.

Mempool policy is implemented by `Blockchain.add_mempool_transaction()` and
related helpers in `netcoin/chain.py`, plus helper policy modules such as
`netcoin/mempool.py`.

## Single Transaction Admission

`Blockchain.add_mempool_transaction()` enforces:

- coinbase transactions are rejected;
- duplicate mempool transaction ids are idempotent;
- expired mempool entries are evicted;
- mempool count and byte caps are respected;
- conflicts require opt-in RBF signaling by all conflicting transactions;
- replacement fee, fee delta, and fee rate must improve on conflicts;
- existing mempool transactions are applied to a temporary UTXO set first;
- the candidate transaction validates against that temporary UTXO set;
- non-fee standardness is checked;
- fee meets `MIN_RELAY_FEE_PER_KB`;
- ancestor limit is not exceeded.

Policy constants live in `netcoin/params.py`, including
`MIN_RELAY_FEE_PER_KB`, `INCREMENTAL_RELAY_FEE`, `DUST_THRESHOLD`,
`MAX_MEMPOOL_TRANSACTIONS`, `MAX_MEMPOOL_BYTES`, `MEMPOOL_EXPIRY_SECONDS`,
`MAX_STANDARD_TX_INPUTS`, `MAX_STANDARD_TX_WEIGHT`, `MAX_MEMPOOL_ANCESTORS`,
and `MAX_MEMPOOL_DESCENDANTS`.

## Package Admission

`Blockchain.add_mempool_package()` implements a compact CPFP/package-relay
primitive. The package MUST be non-empty, must not contain duplicate txids, must
not exceed ancestor limits, must not already be in the mempool, and must not
conflict with existing mempool entries. Transactions are validated in package
order against a temporary UTXO set.

## RBF Boundary

`Transaction.signals_rbf` in `netcoin/tx.py` is true when any input sequence is
below `0xFFFFFFFE`. Replacement policy uses this signal during mempool conflict
handling. This is mempool policy and does not change confirmed-block validity.

## Validation Entry Points

Primary code paths:

- `netcoin/emission.py`: subsidy schedule.
- `netcoin/params.py`: money, reward, and policy constants.
- `netcoin/chain.py`: `subsidy()`, `validate_coinbase_transaction()`,
  `add_mempool_transaction()`, `add_mempool_package()`.
- `netcoin/mempool.py`: standalone mempool policy helpers.
- `netcoin/tx.py`: RBF signaling and transaction size/weight helpers.

Coverage and vectors:

- `tests/test_emission.py`
- `tests/test_supply_emission_api_functional.py`
- `tests/test_mempool_attacks.py`
- `tests/test_mempool_and_coins.py`
- `tests/test_m2_fee_bump.py`
- `core-rs/fixtures/parity-vectors.json` mempool lane
- `core-rs/crates/mempool-core/tests/parity_vectors.rs`
