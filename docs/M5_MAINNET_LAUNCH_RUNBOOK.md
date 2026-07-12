# M5 Mainnet Launch Runbook

Status: **source-ready, evidence required**.

This runbook prepares NetCoin for M5. It does **not** authorize launch. Do **not** claim mainnet is live until strict M5 evidence passes.

## Launch principle

Mainnet is a one-way door. The correct default is **halt**, not launch, whenever evidence is missing.

## Hard launch blockers

- M4 strict evidence missing.
- External audit critical/high issue unresolved.
- Genesis distribution approval missing.
- Legal posture/counsel review missing.
- Release signing verification fails.
- Fewer than 10 independent node operators ready.
- Fewer than 5 independent miners acknowledged.
- Third-party genesis review missing or negative.
- On-call rotation or incident log missing.

## T-4 weeks: feature freeze

Deliverables:

- Feature freeze announcement.
- Final testnet soak start.
- Distribution manifest locked for review.
- Only security, correctness, release, docs, and launch-readiness fixes allowed.

Evidence file: `reports/m5_evidence/feature_freeze.json`

## T-3 weeks: public launch announcement

Deliverables:

- Public launch date or launch window.
- Public genesis distribution draft.
- Risk disclosures.
- Testnet-to-mainnet migration reminder.
- Explicit no-guarantee disclaimer.

Evidence file: `reports/m5_evidence/public_announcement.json`

## T-2 weeks: third-party genesis review

Deliverables:

- Independent reviewer receives genesis config, distribution manifest, and deterministic generation steps.
- Reviewer records hash, comments, and approval/objection.

Evidence file: `reports/m5_evidence/third_party_genesis_review.json`

## T-1 week: signed binaries and pool readiness

Deliverables:

- Final binaries built from tagged commit.
- Checksums generated and signed.
- Public signing keys published.
- Mining pools and independent miners receive launch instructions.

Evidence files:

- `reports/m5_evidence/signed_binaries.json`
- `reports/m5_evidence/mining_pool_acknowledgements.json`

## T-0: genesis ceremony

Deliverables:

- Genesis ceremony log.
- Independent witnesses record exact hash.
- Multiple operators confirm identical genesis hash.
- Launch is halted if any hash mismatch occurs.

Evidence files:

- `reports/m5_evidence/genesis_ceremony.json`
- `reports/m5_evidence/independent_witnesses.json`

## T+1 day

Deliverables:

- 100+ blocks confirmed.
- 5+ independent miners observed.
- No emergency reorg, emergency hard fork, or hidden parameter change.

Evidence files:

- `reports/m5_evidence/first_100_blocks.json`
- `reports/m5_evidence/five_independent_miners.json`

## T+7 days

Deliverables:

- At least one independent operator confirms chain state matches public reference.
- Public state confirmation recorded.

Evidence file: `reports/m5_evidence/t_plus_7_state_confirmation.json`

## T+30 days

Deliverables:

- No unplanned hard fork required.
- Incidents disclosed.
- Launch retrospective written.

Evidence file: `reports/m5_evidence/t_plus_30_stability.json`

## Claim rule

Safe claim before strict evidence:

> M5 source package is ready for launch rehearsal.

Unsafe claim before strict evidence:

> NetCoin mainnet has launched.
