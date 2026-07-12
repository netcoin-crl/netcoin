# Audit Scoping Package

This package is for scoping calls, not an audit claim.

## Suggested firms

- Trail of Bits
- OpenZeppelin
- Kudelski Security
- NCC Group

## Scope to quote

1. Consensus-critical Python implementation.
2. Rust parity crates for consensus/mempool/wallet/signer.
3. Transaction signing, sighash, PSBT, RBF/CPFP, descriptors.
4. Browser wallet vault and signing UX.
5. Faucet abuse controls and API auth.
6. Release signing, SBOM, provenance, and reproducibility process.

## Materials to send

- `docs/PROTOCOL_SPEC.md`
- `docs/THREAT_MODEL.md`
- `docs/BITCOIN_CVE_THREAT_REVIEW.md`
- `architecture/m2-trust-hardening.json`
- latest strict CI output
- parity vector fingerprint and counts

## Questions for firms

- What consensus/vector coverage do you require before starting?
- Do you review browser wallet UX against signing-confusion attacks?
- Can you review both Python and Rust implementations?
- What findings format and retest process do you use?
- What timeline and staffing do you recommend for a Bitcoin-family derivative?

## M4 audit scope marker

For M4 readiness, this package is treated as the audit scope seed. The final
scope must be agreed with the external auditor and recorded in
`reports/m4_evidence/external_audit_completion.json`.
