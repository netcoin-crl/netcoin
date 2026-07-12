# Mainnet protocol specification freeze

This document defines the source-side freeze process for NetCoin's formal
protocol specification. It references `docs/PROTOCOL_SPEC.md` as the canonical
starting point.

## Required freeze artifacts

- Frozen protocol spec hash.
- Parity vector fingerprint.
- Python/Rust/TypeScript compatibility statement.
- Reviewers for consensus, wallet, P2P, and API surfaces.
- Explicit list of known omissions or deferred NIPs.

## Minimum spec scope

The freeze must cover:

- block format,
- transaction format,
- sighash rules,
- address types,
- script/opcode policy,
- proof-of-work and difficulty constants,
- fork-choice and reorg safety,
- mempool policy boundaries,
- P2P handshake and network magic,
- mainnet/testnet separation,
- upgrade activation process.

## Evidence path

Strict M4 requires:

```text
reports/m4_evidence/protocol_spec_freeze.json
```

The evidence file must include the final spec hash, reviewer names, review date,
parity fingerprint, and an explicit `ok: true` attestation.
