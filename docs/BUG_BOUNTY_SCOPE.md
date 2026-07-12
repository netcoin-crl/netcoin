# NetCoin Bug Bounty Scope

Status: draft M2 scope. Funding must be confirmed before this is advertised as
a live paid bounty.

## In scope

- Consensus inflation or invalid spend acceptance.
- Wallet private-key exposure.
- PSBT signing confusion causing loss of funds.
- Faucet abuse bypassing CAPTCHA/rate limits.
- Explorer/API bugs that misreport balances or confirmations.
- Release signing, SBOM, or provenance tampering.

## Out of scope

- Social engineering.
- Denial-of-service without a reproducible proof.
- Vulnerabilities requiring committed secrets.
- Reports against third-party services without permission.

## Draft severity bands

- Critical: consensus inflation, private-key extraction, arbitrary signed release.
- High: unauthorized spend, confirmed balance corruption, signature bypass.
- Medium: persistent wallet confusion, faucet drain bypass, API integrity issue.
- Low: hardening, disclosure, or documentation issues.

## Draft payout ceiling

M2 target: $5,000 top payout. Do not publish this as funded until treasury/legal
approval exists.
