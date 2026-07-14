# Chain Selection And Difficulty

## Genesis

`Blockchain.assert_valid_chain()` in `netcoin/chain.py` reconstructs the
expected genesis block with `create_genesis_block()` and requires:

- the stored height-0 block hash to match the expected genesis;
- height to be `0`;
- previous hash to be `ZERO_HASH`;
- merkle root to match transactions;
- proof of work to be valid.

The frozen genesis fixture is
`tests/fixtures/consensus_vectors/genesis.json`.

## Block Connection

`Blockchain.validate_block_against()` validates a candidate block against a
specific previous block and UTXO set.

The candidate MUST:

- have height `previous.height + 1`;
- reference `previous.hash()` as `previous_hash`;
- satisfy activated header checkpoints;
- be greater than median-time-past;
- use acceptable difficulty bits for the height/timestamp;
- have a correct transaction merkle root;
- have a valid witness commitment when witness data is present;
- satisfy proof of work;
- not be more than two hours in the future;
- not exceed maximum block weight;
- have exactly one coinbase transaction in position 0;
- contain no duplicate transaction ids.

The resulting UTXO set is returned only if all checks pass.

## Fork Choice And Reorgs

Fork and reorg behavior is implemented in `netcoin/chain.py`. The canonical
chain is the valid branch selected by the chain manager's best-chain logic.
Reorg tests exercise competing branches and confirm the node adopts the better
valid branch without accepting invalid blocks.

The localnet harness in `tools/run_localnet.py` includes a real multi-node reorg
scenario in which isolated nodes mine competing tips and then reconnect.

## Headers

Header linkage validation is implemented in:

- `Blockchain.validate_headers_from_tip()` in `netcoin/chain.py`;
- `validate_headers_linked()` in `netcoin/sync.py`.

Headers MUST link by previous hash and height. Header sync is also exercised by
the node HTTP API and localnet harness.

## Difficulty

Difficulty parameters live in `netcoin/params.py`:

- `TARGET_SPACING_SECONDS`
- `DIFFICULTY_ADJUSTMENT_INTERVAL`
- `TARGET_TIMESPAN_SECONDS`
- `SPACING_V2_ACTIVATION_HEIGHT`
- `TARGET_SPACING_V2_SECONDS`
- `INITIAL_BITS`
- `POW_LIMIT_BITS`
- `MIN_DIFFICULTY_GAP_SECONDS`

`target_spacing_at()` and `target_timespan_at()` provide height-dependent target
spacing. The v2 spacing rule activates at `SPACING_V2_ACTIVATION_HEIGHT`.

Proof-of-work target conversion and comparison live in `netcoin/block.py`.
Height/timestamp-specific bit acceptability lives in `netcoin/chain.py`.

## Timestamps

`validate_median_time_past()` in `netcoin/consensus.py` enforces median-time-past
rules. `Blockchain.validate_block_against()` also rejects blocks more than two
hours in the future relative to local time.

## Validation Entry Points

Primary code paths:

- `netcoin/chain.py`: best-chain validation, UTXO application, header
  validation, reorg handling.
- `netcoin/block.py`: target conversion and proof-of-work checks.
- `netcoin/consensus.py`: median-time-past and weight checks.
- `netcoin/sync.py`: linked-header validation and sync scheduling.
- `netcoin/params.py`: difficulty and spacing constants.

Coverage and vectors:

- `tests/test_reorg.py`
- `tests/test_difficulty_v2.py`
- `tests/test_persistent_utxo.py`
- `tests/test_localnet_harness.py`
- `tools/run_localnet.py`
- `core-rs/fixtures/parity-vectors.json` consensus lane
