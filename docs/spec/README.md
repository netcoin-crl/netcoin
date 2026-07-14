# NetCoin Protocol Specification

This directory is the source-level protocol specification and external-audit
scope packet for NetCoin's UTXO proof-of-work testnet implementation.

NetCoin is Bitcoin-family software for a public testnet. This specification
describes the behavior implemented in this repository. It is not a mainnet
launch claim, an external audit report, or a governance approval for future
mainnet parameters.

Normative keywords use the usual meanings:

- MUST and MUST NOT describe behavior required for this implementation.
- SHOULD describes expected behavior where operator policy can vary.
- MAY describes optional behavior or non-consensus tooling.
- Non-normative notes explain intent and compatibility boundaries.

## Scope

The spec covers:

- block headers, block bodies, proof of work, merkle roots, witness commitment;
- transaction encoding, txid/wtxid, coinbase and regular transaction validity;
- signature hash modes and signature verification;
- supported scripts and address encodings;
- chain selection, fork handling, timestamps, difficulty, and headers;
- emission and mempool policy;
- node HTTP/P2P messages, peer discovery, compact blocks, and relay.

Out of scope:

- governance, legal, custody, exchange, market, or liquidity decisions;
- mainnet genesis or mainnet versionbits activation;
- hosted wallet UX and PSBT airgap flows owned by the wallet lane;
- app-layer markets or account systems.

## File Layout

- [Block Format](block-format.md)
- [Transaction Format](transaction-format.md)
- [Sighash And Signatures](sighash-and-signatures.md)
- [Script And Addresses](script-and-addresses.md)
- [Chain Selection And Difficulty](chain-selection-and-difficulty.md)
- [Emission And Mempool Policy](emission-and-mempool-policy.md)
- [P2P And Node API](p2p-and-node-api.md)

## Code And Vector Matrix

| Spec section | Primary implementation | Tests and vectors |
|---|---|---|
| Block format | `netcoin/block.py`, `netcoin/chain.py`, `netcoin/consensus.py`, `netcoin/serialization.py`, `netcoin/params.py` | `tests/test_protocol_vectors.py`, `tests/fixtures/consensus_vectors/genesis.json`, `core-rs/fixtures/parity-vectors.json`, `core-rs/crates/consensus/tests/parity_vectors.rs` |
| Transaction format | `netcoin/tx.py`, `netcoin/serialization.py`, `netcoin/chain.py` | `tests/test_protocol_vectors.py`, `tests/test_binary_codec.py`, `core-rs/fixtures/parity-vectors.json` |
| Sighash and signatures | `netcoin/tx.py`, `netcoin/script.py`, `netcoin/crypto.py` | `tests/test_sighash.py`, `tests/test_message_signing.py`, `core-rs/crates/signer-core/src/lib.rs` |
| Script and addresses | `netcoin/script.py`, `netcoin/crypto.py`, `netcoin/taproot.py`, `netcoin/params.py` | `tests/test_script_vm.py`, `tests/test_taproot_scriptpath.py`, `tests/test_address_and_config.py`, `core-rs/fixtures/parity-vectors.json` |
| Chain selection and difficulty | `netcoin/chain.py`, `netcoin/block.py`, `netcoin/consensus.py`, `netcoin/sync.py`, `netcoin/params.py` | `tests/test_reorg.py`, `tests/test_difficulty_v2.py`, `tests/test_localnet_harness.py`, `tools/run_localnet.py` |
| Emission and mempool policy | `netcoin/emission.py`, `netcoin/mempool.py`, `netcoin/chain.py`, `netcoin/params.py` | `tests/test_emission.py`, `tests/test_mempool_attacks.py`, `tests/test_mempool_and_coins.py`, `core-rs/crates/mempool-core/tests/parity_vectors.rs` |
| P2P and node API | `netcoin/node.py`, `netcoin/p2p.py`, `netcoin/addrv2.py`, `netcoin/compact.py`, `netcoin/sync.py`, `netcoin/peerdb.py` | `tests/test_p2p_messages.py`, `tests/test_p2p_node_sync.py`, `tests/test_remaining_code_upgrades.py`, `tests/test_localnet_harness.py`, `core-rs/crates/node/src/lib.rs` |

## Consensus Boundaries

Consensus validation is the subset of behavior that decides whether blocks and
transactions are valid in the active chain. Policy behavior, including mempool
standardness, relay limits, API throttles, peer scoring, and wallet decisions,
MUST NOT be treated as consensus unless explicitly called out in the relevant
section.

The implementation entry point for block validation is
`Blockchain.validate_block_against()` in `netcoin/chain.py`. The entry point for
transaction validation inside blocks is `Blockchain.validate_regular_transaction()`.
Mempool admission uses those same transaction checks plus policy checks.

## Parity Vectors

The consolidated parity vector file is `core-rs/fixtures/parity-vectors.json`.
It currently contains lanes for `consensus`, `wallet`, `markets`, `api`,
`mempool`, `signer`, `p2p`, and `indexer`. P1 only references those lanes; it
does not modify vectors or Rust parity code.

The frozen genesis fixture is
`tests/fixtures/consensus_vectors/genesis.json`.

## Change Discipline

Any future consensus rule change SHOULD update this specification, add or update
parity vectors, and run the relevant Python/Rust/TypeScript parity lanes before
activation. Mainnet versionbits and mainnet genesis remain governance-gated and
are not wired by this spec.
