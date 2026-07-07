# NetCoin Protocol Specification

NetCoin is an educational Bitcoin-like testnet. This specification documents the wire-visible and consensus-relevant rules that another implementation should follow for compatibility.

## Scope

This document covers block headers, transactions, addresses, signatures, proof-of-work, mempool policy, wallet test vectors, and app-layer boundaries. App-layer features such as invoices, markets, webhooks, and community tools do not change block validity rules.

## Network Parameters

- Ticker: NET
- Target block interval: 600 seconds
- Network magic: exposed by `netcoin.params.NETWORK_MAGIC`
- Genesis difficulty bits: exposed by `netcoin.params.GENESIS_BITS`
- Difficulty target conversion: `netcoin.block.bits_to_target(bits)`

## Block Header

A block header contains:

1. `version`
2. `previous_hash`
3. `merkle_root`
4. `timestamp`
5. `bits`
6. `nonce`
7. `height`

Headers serialize through `netcoin.serialization.serialize_header`. A block hash is the chain's canonical header hash as implemented by `Block.hash()`.

## Transactions

A transaction contains ordered inputs, ordered outputs, locktime, and optional witness data. The txid excludes witness data and the wtxid commits to witness data. Serialization helpers live in `netcoin.serialization` and transaction validation lives in `netcoin.chain.Blockchain.validate_regular_transaction`.

## Addresses and Scripts

Supported wallet addresses include:

- legacy P2PKH
- SegWit-style P2WPKH
- Taproot-style P2TR
- P2SH multisig and P2SH-wrapped SegWit helpers

The script module supports standard script construction, multisig redeem scripts, timelocks, and address descriptors.

## Signatures

NetCoin supports deterministic ECDSA-style signatures and Taproot-style Schnorr paths in the educational implementation. Signature hash behavior and script validation are covered by the test suite under `tests/test_sighash.py`, `tests/test_script_vm.py`, and Taproot tests.

## Mempool Policy

Mempool policy is not consensus, but professional nodes should use the same default policy to reduce spam and user confusion:

- reject coinbase transactions submitted through mempool
- reject dust outputs
- enforce minimum relay fee
- enforce standard transaction weight
- enforce ancestor and descendant limits
- allow opt-in replacement only when replacement fee rules are met

## App-Layer Boundary

App-layer APIs are local operator state. They can require API keys, signed actions, idempotency keys, and nonces, but they must not change consensus rules.

## Test Vectors

Run:

```bash
python tools/professional_readiness.py --vectors
# or
netcoin professional-check --vectors
```

The generated vectors include a fixed private key, public keys, addresses, sample transaction ids, a sample block hash, wallet KDF parameters, and network constants.
