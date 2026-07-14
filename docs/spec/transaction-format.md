# Transaction Format

## Object Model

Transactions are implemented in `netcoin/tx.py`:

- `Transaction`
- `TxInput`
- `TxOutput`
- `SpendableOutput`

Amounts are integer satoshis. `COIN` is `100_000_000` satoshis and
`MAX_MONEY` is defined in `netcoin/params.py`.

## Inputs

A `TxInput` contains:

- `txid`: 32-byte hex previous transaction id;
- `vout`: previous output index;
- `signature`: legacy signature field;
- `public_key`: legacy public key field;
- `coinbase`: coinbase data for coinbase inputs;
- `script_sig`: scriptSig for script-template spending;
- `witness`: witness stack items;
- `sequence`: uint32 sequence value.

`TxInput.__post_init__()` requires a 32-byte hex `txid`, normalizes it to
lowercase, normalizes witness items to lowercase strings, and requires sequence
to fit uint32.

## Outputs

A `TxOutput` contains:

- `amount`: non-negative satoshis;
- `address`: optional NetCoin address;
- `script_pubkey`: optional explicit locking script.

Positive outputs MUST provide either an address or a script pubkey. Positive
address outputs MUST pass `validate_address()` from `netcoin/crypto.py`.
Outputs MUST NOT exceed `MAX_MONEY`.

`effective_script_pubkey()` returns the explicit script when present, otherwise
it derives one from the address through `address_to_script_pubkey()` in
`netcoin/script.py`.

## Transaction Body

A `Transaction` contains:

- `version`: integer, default `1`;
- `inputs`: non-empty list of inputs;
- `outputs`: list of outputs;
- `locktime`: uint32 locktime.

Transactions MUST have at least one input. `locktime` MUST fit uint32.
Regular transactions MUST have at least one output during chain validation.

## Serialization And Hashes

`Transaction.serialize()` returns canonical JSON. `Transaction.to_bytes()` uses
`serialize_transaction()` in `netcoin/serialization.py`.

Hash identifiers:

- `txid()` is double SHA256 over the transaction including scripts but excluding
  witness data.
- `wtxid()` is double SHA256 over the transaction including scripts and witness.
- `stripped_txid()` excludes scripts and witness.

This preserves legacy JSON txid compatibility while supporting a SegWit-shaped
txid/wtxid split.

## Coinbase

`Transaction.is_coinbase` is true only when:

- the transaction has one input;
- the input spends `ZERO_HASH:-1`;
- the input has non-empty `coinbase` data.

Coinbase transactions MUST NOT appear outside block position 0. Regular mempool
admission rejects coinbase transactions.

## Regular Transaction Validation

`Blockchain.validate_regular_transaction()` in `netcoin/chain.py` enforces:

- transaction is not coinbase;
- outputs are present;
- inputs are unique;
- locktime is final for the spend height/time;
- output total is positive and not above `MAX_MONEY`;
- each input spends an existing unspent output;
- immature coinbase outputs cannot be spent before `COINBASE_MATURITY`;
- each input signature/script verifies;
- input total is not below output total;
- input total is not above `MAX_MONEY`.

The returned value is the transaction fee in satoshis.

## Binary Codec Boundary

Raw transaction hex export exists through `raw_hex()`. Full raw binary
transaction decoding intentionally raises `TransactionError` in
`Transaction.from_hex()` and callers must use JSON import/export for now.

## Validation Entry Points

Primary code paths:

- `netcoin/tx.py`: transaction object model, txid/wtxid, sighash.
- `netcoin/serialization.py`: binary transaction and weight/vsize helpers.
- `netcoin/chain.py`: chain and mempool transaction validation.
- `netcoin/script.py`: script templates and script verification.

Coverage and vectors:

- `tests/test_protocol_vectors.py`
- `tests/test_binary_codec.py`
- `tests/test_netcoin.py`
- `core-rs/fixtures/parity-vectors.json` consensus lane
