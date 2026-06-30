# NetCoin External Security Review Plan

NetCoin is **educational testnet software**. This document is the checklist of what
must be independently reviewed and resolved **before any mainnet discussion**. None
of this is a promise that NetCoin will ever have a mainnet — it is a gate, not a plan
to launch.

> Hard rule: do not make any real-money, investment, or profit claims about NetCoin,
> and do not launch a mainnet, until every item below has an external sign-off.

## 1. Consensus & validation

- [ ] Independent review of block/transaction validation (`chain.py`, `block.py`, `tx.py`).
- [ ] Reorg logic reviewed for deep reorgs, equal-work ties, and rollback correctness.
- [ ] No integer overflow / money-supply violations (cap, reward reduction, subsidy, fees).
- [ ] Coinbase maturity and double-spend protections audited.
- [ ] Difficulty retargeting reviewed for manipulation (timestamp games).
- [ ] Deterministic serialization / txid stability reviewed.

## 2. Cryptography

- [ ] secp256k1 ECDSA and BIP340 Schnorr implementations reviewed (or replaced with a vetted library).
- [ ] Address formats (Base58Check, Bech32, Bech32m) reviewed against test vectors.
- [ ] Wallet encryption reviewed end to end: ChaCha20-Poly1305 AEAD integration,
      PBKDF2 parameters, associated-data handling, legacy-wallet migration, and
      dependency supply-chain risk.
- [ ] RNG sources audited (`secrets`), no key reuse.

## 3. Networking / P2P

- [ ] DoS review of all node endpoints (body size, rate, connection limits).
- [ ] Peer gossip reviewed for poisoning, eclipse, and amplification.
- [ ] TCP P2P transport reviewed for malformed frames, slowloris, connection
      limits, and resource exhaustion.
- [ ] Sync logic reviewed for resource exhaustion (huge chains, slowloris).
- [ ] No trust placed in unauthenticated `X-Forwarded-For` beyond a trusted proxy.
- [ ] TLS / transport security for any non-local traffic.

## 4. Wallet & key handling

- [ ] Seed-phrase scheme reviewed (entropy, checksum, recovery).
- [ ] Key export warnings and encrypted-unlock UX reviewed.
- [ ] No key material logged or written outside the wallet file.

## 5. Public services

- [ ] Faucet abuse review (rate limits, CAPTCHA, balance limits, hot-wallet exposure).
- [ ] Explorer reviewed for injection/XSS in generated HTML and any API.
- [ ] RPC kept private/authenticated; never exposed publicly.
- [ ] Monitoring/alerting cannot leak secrets.

## 6. Operations & supply chain

- [ ] Reproducible builds verified by a third party.
- [ ] Release artifacts signed (GPG) and signatures verified independently.
- [ ] Deploy/upgrade scripts reviewed for safe data handling and rollback.
- [ ] Backups tested by an actual restore drill.
- [ ] Dependency review (`cryptography` is the intentional wallet-AEAD dependency;
      keep everything else minimal).

## 7. Testing evidence

- [ ] Full automated suite passing on every seed and in CI.
- [ ] Fuzzing run for an extended period with no crashes.
- [ ] Adversarial testnet exercise (hostile nodes/miners) completed.

## 8. Legal & disclosure

- [ ] `SECURITY.md` has a real, monitored reporting contact.
- [ ] Coordinated disclosure policy published.
- [ ] Independent legal review of any token/network claims.

## Sign-off

| Area | Reviewer | Date | Result |
|---|---|---|---|
| Consensus | | | |
| Cryptography | | | |
| Networking | | | |
| Wallet | | | |
| Services | | | |
| Operations | | | |

No mainnet discussion proceeds until every box is checked and every row is signed off.
