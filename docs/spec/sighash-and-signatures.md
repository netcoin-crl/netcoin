# Sighash And Signatures

## Supported Sighash Flags

Sighash constants live in `netcoin/tx.py`:

- `SIGHASH_ALL = 0x01`
- `SIGHASH_NONE = 0x02`
- `SIGHASH_SINGLE = 0x03`
- `SIGHASH_ANYONECANPAY = 0x80`

`SIGHASH_ALL` is the default. Bare 64-byte signatures are treated as
`SIGHASH_ALL` for backward compatibility. Non-default signatures append one flag
byte.

## Digest Construction

`Transaction.sighash()` is the normative implementation.

For `SIGHASH_ALL`, the digest commits to:

- transaction version;
- all inputs without scripts or witness;
- all outputs;
- locktime;
- signing input index;
- the selected previous output;
- marker string `NETCOIN_ALL`.

For non-default flags:

- `SIGHASH_NONE` commits to no outputs.
- `SIGHASH_SINGLE` commits only to the output at the same index as the signing
  input and fails if no matching output exists.
- `SIGHASH_ANYONECANPAY` commits only to the selected input's previous output
  rather than the full input list.
- `SIGHASH_NONE` and `SIGHASH_SINGLE` zero other inputs' sequence numbers when
  `ANYONECANPAY` is not set.

Unknown base sighash types MUST fail with `TransactionError`.

## Signature Placement

`Transaction.sign_input()` signs one input according to the previous output's
script template:

- P2WPKH places signature and public key in witness.
- P2PKH places signature and public key in legacy fields/scriptSig shape.
- Taproot-style paths use the x-only public key and Schnorr helpers.
- Multisig/script cases use script and witness conventions implemented in
  `netcoin/script.py`.

`Transaction.verify_input()` verifies the selected input against the previous
output and dispatches through `verify_script()` or the direct signature helpers
as appropriate.

## Crypto Primitives

Signature and address primitives live in `netcoin/crypto.py`:

- `ecdsa_sign()` / `ecdsa_verify()`
- `schnorr_sign()` / `schnorr_verify()`
- `private_key_to_public_key()`
- `private_key_to_xonly_public_key()`
- `public_key_to_address()`
- `validate_address()`

The implementation supports a pure-Python path and optional accelerated crypto
when configured elsewhere. This spec describes the byte-level behavior, not a
specific provider implementation.

## Script Verification Boundary

Script-level signature opcodes are implemented in `netcoin/script.py`:

- `OP_CHECKSIG`
- `OP_CHECKSIGVERIFY`
- `OP_CHECKMULTISIG`
- `OP_CHECKMULTISIGVERIFY`

The `ScriptContext` object supplies the transaction, input index, previous
output, block height, and block time to script execution.

## Validation Entry Points

Primary code paths:

- `netcoin/tx.py`: `Transaction.sighash()`, `sign_input()`,
  `verify_input()`, `_split_sighash()`, `_append_sighash()`.
- `netcoin/script.py`: `ScriptContext`, `execute_script()`,
  `verify_script()`.
- `netcoin/crypto.py`: ECDSA/Schnorr/address primitives.

Coverage and vectors:

- `tests/test_sighash.py`
- `tests/test_message_signing.py`
- `tests/test_script_vm.py`
- `core-rs/fixtures/parity-vectors.json` signer lane
- `core-rs/crates/signer-core/src/lib.rs`
