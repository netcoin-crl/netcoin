# Block Format

## Header

A NetCoin block header is represented by `BlockHeader` in `netcoin/block.py`.
The consensus-facing fields are:

- `version`: integer block version.
- `previous_hash`: 32-byte lowercase hex hash of the parent block.
- `merkle_root`: 32-byte lowercase hex transaction merkle root.
- `timestamp`: integer Unix timestamp.
- `bits`: compact proof-of-work target.
- `nonce`: integer nonce.
- `height`: integer block height.

`BlockHeader.__post_init__()` normalizes integer fields and lowercases hash
fields. `previous_hash` and `merkle_root` MUST be 64 lowercase hexadecimal
characters after normalization. `BlockHeader.hash()` is double SHA256 over the
canonical JSON header representation.

Binary header serialization is available through `netcoin/serialization.py` via
`serialize_header()`. JSON import/export remains the compatibility format for
older chain data and public node APIs.

## Block Body

A block is represented by `Block` in `netcoin/block.py` and contains:

- `header`: the `BlockHeader`.
- `transactions`: a non-empty list of `Transaction` objects.

`Block.__post_init__()` rejects empty transaction lists. The first transaction
MUST be coinbase. Later transactions MUST NOT be coinbase. These rules are
enforced by `Blockchain.validate_block_against()` in `netcoin/chain.py`.

## Merkle Root

`merkle_root()` in `netcoin/block.py` computes the block transaction merkle root
from each transaction's `txid()`. When a merkle layer has odd length, the final
hash is duplicated before hashing pairs. Empty transaction lists return
`ZERO_HASH`, but blocks themselves are not allowed to have empty transaction
lists.

`Blockchain.validate_block_against()` requires
`block.header.merkle_root == merkle_root(block.transactions)`.

## Witness Commitment

NetCoin has a SegWit-shaped witness commitment implemented in
`netcoin/block.py`:

- `witness_merkle_root()` uses `wtxid()` values.
- `witness_commitment_root()` treats the coinbase witness hash as zero to avoid
  a circular commitment.
- `witness_commitment()` commits to `witness_root || reserved_value`.
- `WITNESS_COMMITMENT_PREFIX` is
  `OP_RETURN NETCOIN_WITNESS_COMMITMENT`.

If any non-coinbase transaction has witness data,
`block_requires_witness_commitment()` is true and the coinbase MUST contain the
matching commitment. `validate_witness_commitment()` enforces this rule during
block validation.

## Proof Of Work

Proof-of-work compact targets are implemented by `bits_to_target()`,
`target_to_bits()`, and `check_proof_of_work()` in `netcoin/block.py`.

Rules:

- compact targets MUST be positive;
- negative compact targets are invalid;
- targets above the POW limit are invalid;
- a header is valid only when `int(header.hash(), 16) <= bits_to_target(bits)`.

The POW limit and initial compact target come from `POW_LIMIT_BITS` and
`INITIAL_BITS` in `netcoin/params.py`.

## Block Weight

`Block.weight()` delegates to `block_weight()` in `netcoin/serialization.py`.
`validate_block_weight_limit()` in `netcoin/consensus.py` checks the
`MAX_BLOCK_WEIGHT` limit from `netcoin/params.py`. Blocks above the maximum
weight MUST be rejected.

## Coinbase

The first transaction MUST be coinbase. `Transaction.is_coinbase` in
`netcoin/tx.py` requires:

- exactly one input;
- input `txid` equal to `ZERO_HASH`;
- input `vout` equal to `-1`;
- a non-empty `coinbase` field.

`Blockchain.validate_coinbase_transaction()` requires coinbase output total to
be within the money range, not exceed subsidy plus fees, and be positive for
non-genesis blocks.

## Validation Entry Points

Primary code paths:

- `netcoin/block.py`: `BlockHeader`, `Block`, merkle roots, POW, witness
  commitments.
- `netcoin/chain.py`: `Blockchain.validate_block_against()`,
  `Blockchain.assert_valid_chain()`.
- `netcoin/consensus.py`: median-time-past and block weight checks.
- `netcoin/params.py`: constants such as `ZERO_HASH`, `MAX_BLOCK_WEIGHT`,
  `INITIAL_BITS`, and `POW_LIMIT_BITS`.

Coverage and vectors:

- `tests/test_protocol_vectors.py`
- `tests/fixtures/consensus_vectors/genesis.json`
- `core-rs/fixtures/parity-vectors.json` consensus lane
- `core-rs/crates/consensus/tests/parity_vectors.rs`
