# Bitcoin CVE Threat Review for NetCoin M2

This is a source-level review checklist. It is not an external audit.

## Review themes

1. inflation bugs from duplicate inputs or malformed coinbase rules.
2. Signature-hash confusion and signature replay.
3. Transaction malleability and witness/txid mismatches.
4. Merkle tree duplicate-leaf ambiguity.
5. Difficulty/retarget edge cases.
6. Time-warp and timestamp manipulation.
7. Orphan/reorg handling.
8. Mempool replacement policy bypass.
9. Dust and resource exhaustion.
10. Script evaluation inconsistencies.
11. Address-type confusion.
12. Wallet change-output confusion.
13. PSBT signing of wrong network or path.
14. Hardware-wallet blind signing.
15. Release artifact substitution.

## M2 mitigation hooks

- Parity vectors across Python/Rust/TypeScript.
- Source and strict M2 readiness gates.
- Hardware signing transcripts requiring address, fee, tx, and change review.
- RBF/CPFP tests using existing mempool policy.
- SBOM and provenance generation.
- Bug bounty and audit scoping package.

## Strict completion requirement

Every high-risk CVE class above needs either a passing test, a documented
non-applicability rationale, or an audit waiver before mainnet readiness.
