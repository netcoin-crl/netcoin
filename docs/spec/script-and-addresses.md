# Script And Addresses

## Script Representation

NetCoin scripts are represented as canonical token strings in
`netcoin/script.py`. `canonical_script()` normalizes token lists into the script
string form used by transaction JSON and tests.

Supported standard templates include:

- P2PKH: `OP_DUP OP_HASH160 <hash160> OP_EQUALVERIFY OP_CHECKSIG`
- P2SH: `OP_HASH160 <script_hash> OP_EQUAL`
- P2WPKH: `OP_0 <20-byte-pubkey-hash>`
- P2WSH: `OP_0 <32-byte-script-hash>`
- Taproot-style key path: `OP_1 <xonly-pubkey>`
- Multisig: `OP_M <pubkeys...> OP_N OP_CHECKMULTISIG`
- CLTV helper scripts containing `OP_CHECKLOCKTIMEVERIFY`

`classify_script()` identifies these standard templates.

## Opcode Set

`execute_script()` in `netcoin/script.py` implements the supported opcode set.
Major groups include:

- flow control: `OP_IF`, `OP_NOTIF`, `OP_ELSE`, `OP_ENDIF`;
- stack operations: `OP_DUP`, `OP_DROP`, `OP_SWAP`, `OP_OVER`, `OP_NIP`,
  `OP_TUCK`, `OP_ROT`, `OP_2DUP`, `OP_DEPTH`, `OP_IFDUP`;
- hashes: `OP_HASH160`, `OP_SHA256`, `OP_HASH256`, `OP_RIPEMD160`;
- arithmetic/comparison: `OP_ADD`, `OP_SUB`, `OP_MIN`, `OP_MAX`,
  `OP_BOOLAND`, `OP_BOOLOR`, `OP_NUMEQUAL`, `OP_NUMEQUALVERIFY`,
  `OP_NUMNOTEQUAL`, `OP_LESSTHAN`, `OP_GREATERTHAN`,
  `OP_LESSTHANOREQUAL`, `OP_GREATERTHANOREQUAL`, `OP_WITHIN`;
- unary numeric operations: `OP_NEGATE`, `OP_ABS`, `OP_NOT`,
  `OP_0NOTEQUAL`, `OP_1ADD`, `OP_1SUB`;
- validation: `OP_VERIFY`, `OP_EQUAL`, `OP_EQUALVERIFY`,
  `OP_CHECKSIG`, `OP_CHECKSIGVERIFY`, `OP_CHECKMULTISIG`,
  `OP_CHECKMULTISIGVERIFY`;
- timelocks: `OP_CHECKLOCKTIMEVERIFY`, `OP_CHECKSEQUENCEVERIFY`;
- constants: `OP_0`, `OP_1` through `OP_16`, `OP_1NEGATE`.

`OP_RETURN` fails script execution when encountered.

## Address Encoding

Address and key version parameters live in `netcoin/params.py`:

- `P2PKH_ADDRESS_VERSION`
- `P2SH_ADDRESS_VERSION`
- `WIF_VERSION`
- `BECH32_HRP`
- `BECH32M_HRP`
- `WITNESS_HRP`

Address creation and validation live in `netcoin/crypto.py`:

- `public_key_to_address()`
- `public_key_to_p2wpkh_address()`
- `public_key_to_taproot_address()`
- `validate_address()`
- `address_type()`

NetCoin intentionally does not reuse Bitcoin mainnet address prefixes.

## Address To Script

`address_to_script_pubkey()` in `netcoin/script.py` is the normative conversion
from supported address types to locking scripts. `TxOutput.effective_script_pubkey()`
uses the explicit script when present and otherwise derives the script from the
address.

## Taproot-Style Boundary

Taproot-style helpers are implemented in `netcoin/taproot.py` and referenced by
transaction signing and script tests. The implementation is educational and
NetCoin-specific; it is not a claim of byte-for-byte Bitcoin Taproot consensus
compatibility.

## Validation Entry Points

Primary code paths:

- `netcoin/script.py`: script templates, opcode execution, script verification.
- `netcoin/crypto.py`: address encoding/validation and signature primitives.
- `netcoin/taproot.py`: Taproot-style helpers.
- `netcoin/params.py`: address and witness HRP constants.
- `netcoin/tx.py`: transaction signing and script dispatch.

Coverage and vectors:

- `tests/test_script_vm.py`
- `tests/test_taproot_scriptpath.py`
- `tests/test_address_and_config.py`
- `tests/test_netcoin.py`
- `core-rs/fixtures/parity-vectors.json` wallet and signer lanes
