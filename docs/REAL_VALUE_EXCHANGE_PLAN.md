# NetCoin Real-Value Exchange Plan — Execution Checklists

Dependency-ordered, checklist-driven roadmap for taking NetCoin from an
educational testnet to a network whose coin carries real monetary value and
can be exchanged for fiat and other crypto. Every item is a concrete action
with a deliverable — a file to create, a command to run, a test that must
pass, or a document that must be signed.

**Ground rules:**

- Phases 0–3 are engineering, executable in this repo.
- Phase 4 is legal/financial and requires licensed professionals and capital.
  **Operating a real-value exchange without Phase 4 is illegal in most
  jurisdictions.** Nothing here is legal advice.
- A checkbox is done when its deliverable exists and its verification command
  passes — not before.
- Effort estimates: one experienced engineer + AI-assisted development,
  calendar time.

**How to track:** check boxes in this file via PRs; each phase ends with an
exit-gate checklist that mirrors the evidence-gate pattern already in
`netcoin/mainnet_readiness.py`.

---

# Phase 0 — Consensus & protocol hardening

## 0.1 Protocol specification freeze  *(1–2 weeks)*

**Deliverable:** frozen spec + CI guard that blocks consensus edits without a NIP.

- [ ] Build the consensus-file inventory. Create
      `docs/spec/CONSENSUS_SURFACE.md` listing every consensus-critical path:
      - `netcoin/chain.py` — `validate_block_against`, `load_or_create`,
        reorg/most-work selection, `_atomic_write_json`
      - `netcoin/transaction.py` — sighash types, weight, serialization
      - script VM module — opcode semantics, flags
      - `netcoin/emission.py` — subsidy schedule
      - `netcoin/params.py` — `REWARD_REDUCTION_INTERVAL`,
        `REWARD_SCHEDULE_ACTIVATION_HEIGHT`, `LEGACY_NRE_ACTIVATION_HEIGHT`,
        network magic, ports
- [ ] Cross-check each `docs/spec/` section against code. For every rule in
      the spec, cite the enforcing function + the test that pins it
      (`tests/test_p1_protocol_spec_docs.py` is the anchor — extend it to
      assert every `CONSENSUS_SURFACE.md` entry appears in the spec).
- [ ] Tag the spec: add `SPEC_VERSION = "1.0.0"` to `netcoin/params.py` and
      a matching header line in `docs/spec/README`.
- [ ] Write the NIP process doc `docs/spec/NIP_PROCESS.md`: numbered
      proposals, required sections (motivation, spec diff, activation method,
      backout plan), versionbits activation only
      (rehearsal tooling exists: `tests/test_p3_versionbits_rehearsal.py`).
- [ ] Add the CI guard: `.github/workflows/consensus-guard.yml` — job fails
      if `git diff origin/main --name-only` touches any `CONSENSUS_SURFACE.md`
      file while neither `SPEC_VERSION` changed nor commit message contains
      `NIP-`. Test the guard with a deliberate violating PR.
- [ ] Get one external reviewer to read spec-vs-code and sign
      `docs/MAINNET_PROTOCOL_SPEC_FREEZE.md` (name, date, commit hash).

**Verify:** `pytest tests/test_p1_protocol_spec_docs.py` green; violating PR
blocked by CI; freeze doc has ≥1 external signature.

## 0.2 Monetary policy lock  *(2–3 days)*

**Deliverable:** machine-verified total supply; policy doc ratified.

- [ ] Write `tools/compute_total_supply.py`: iterate the emission schedule
      (50 NET start, −10% per 265,000 blocks, integer-sats rounding exactly
      as `netcoin/emission.py` does) until subsidy hits 0; print total
      supply, final emission height, per-era table.
- [ ] Add `tests/test_total_supply.py`: asserts the computed total equals a
      hardcoded published constant; asserts era boundaries (heights 265000,
      530000, …) match `emission.py` output block-by-block at boundaries ±1.
- [ ] Publish the number: add the supply table to
      `docs/MAINNET_MONETARY_POLICY.md` and the learn site economics card
      (`sites/learn/index.html#economics`), and add a test that greps both
      for the same constant so copy can't drift.
- [ ] Sign off `docs/MAINNET_MONETARY_POLICY.md` (name, date, commit).

**Verify:** `python tools/compute_total_supply.py` output matches doc;
`pytest tests/test_total_supply.py` green.

## 0.3 External security audit  *(3–4 months calendar; $50k–150k)*

**Deliverable:** published report, zero open critical/high findings.

- [ ] Finalize `docs/AUDIT_SCOPING_PACKAGE.md`: LoC per module
      (`cloc netcoin/`), architecture diagram, threat model, list of
      out-of-scope items (sites JS, markets sandbox).
- [ ] Request quotes from 3 firms (Trail of Bits, Kudelski, Least Authority,
      NCC, Zellic). Email the scoping package; ask for: timeline, team CVs,
      fixed price, re-verification terms.
- [ ] Select firm; sign SoW; book start date (expect 1–3 months lead).
- [ ] Create audit branch `audit/YYYY-MM` from a tagged release; freeze all
      consensus work on it for the engagement.
- [ ] Pre-audit self-check (auditors bill for what you could have caught):
      - [ ] 0.5 fuzzing has ≥2 weeks of green nights
      - [ ] `pytest -q` fully green (currently 896–900 passing)
      - [ ] `tests/test_security_regressions.py` reviewed for gaps vs the
            threat model
- [ ] Receive report → log every finding in
      `docs/MAINNET_AUDIT_FINDINGS_REGISTER.md` with: ID, severity, file,
      description, fix commit, re-verify status.
- [ ] Fix all critical/high; request re-verification letter.
- [ ] Publish report + register on `sites/security/`.

**Verify:** register shows 0 open critical/high; report URL live; firm's
re-verification letter on file.

## 0.4 Findings register stays alive  *(ongoing)*

- [ ] Add register entry template + rule to `docs/SECURITY_REVIEW_PLAN.md`:
      every future external report (bug bounty, pentest) lands in the same
      register within 48h of receipt.
- [ ] Add a `tools/check_findings_register.py` that fails if any entry has
      severity critical/high and status ≠ fixed+verified older than 30 days;
      wire into CI weekly.

## 0.5 Sustained fuzzing in CI  *(1 week to wire, then calendar)*

**Deliverable:** nightly fuzz workflow, cached corpus, crash → red build.

- [ ] Create `.github/workflows/nightly-fuzz.yml`:
      - schedule: `cron: "0 8 * * *"`
      - restore corpus from actions cache (key `fuzz-corpus-v1`)
      - run `python tools/run_nightly_fuzz_accumulator.py --iterations
        200000 --history-dir .fuzz-history --out reports/nightly-fuzz.json`
      - save corpus + history back to cache
      - upload `reports/nightly-fuzz.json` as artifact
      - fail job if report `ok: false`
- [ ] Add missing fuzz targets to the accumulator (current: tx-dict, rawtx,
      script):
      - [ ] P2P binary message decoder (frame parsing, length fields,
            truncation) — feed random + mutated valid frames
      - [ ] compact-block reconstruction (`test_remaining_code_upgrades.py`
            has the valid-path tests; fuzz the missing-tx request path)
      - [ ] PSBT parser (base64 + binary)
- [ ] Auto-regression: on crash, accumulator writes the input to
      `tests/fuzz_regressions/<target>/<hash>.bin`; add
      `tests/test_fuzz_regressions.py` that replays every file in that dir
      through the target parser asserting no exception escape.
- [ ] Surface cumulative counts: status site card reading the latest
      history summary (`accumulate_fuzz_history` output — already tested in
      `tests/test_wave1_3_fuzz_accumulator.py`).

**Verify:** 30 consecutive green nightly runs; ≥10M cumulative cases;
`pytest tests/test_fuzz_regressions.py` green.

## 0.6 Adversarial economics testing  *(2–3 weeks)*

**Deliverable:** measured reorg-risk table that sets deposit confirmation
policy; time-warp boundary tests.

- [ ] Extend the localnet harness with an attacker role:
      `tools/run_attack_drill.py --scenario <name>` building on
      `netcoin/soak.py` and the chaos drill
      (`tests/test_wave1_4_chaos_drill.py`). Attacker capabilities: withhold
      mined blocks N seconds, mine on private tip, release on trigger.
- [ ] Script five scenarios, each emitting a JSON report:
      - [ ] `selfish-mining`: attacker at 10/20/30/40% hashrate ×1000 rounds
            → measure revenue share vs fair share
      - [ ] `deposit-doublespend`: deposit tx confirmed k blocks deep,
            attacker reorgs with 10–45% hashrate → success probability per
            (k, hashrate) cell
      - [ ] `fee-sniping`: high-fee block reorg incentive at tip
      - [ ] `time-warp`: timestamps at median-time-past and future-clamp
            boundaries attempting difficulty manipulation
      - [ ] `mempool-flood`: sustained max-weight junk at real feerates →
            node RSS (via `/debug/memory`), relay latency, eviction behavior
- [ ] Write `docs/REORG_RISK_TABLE.md` from `deposit-doublespend` output:
      success probability matrix (confirmations × attacker hashrate). This
      file is the cited source for 2.3's confirmation policy.
- [ ] Add boundary unit tests for the difficulty clamp rules found in
      `time-warp` (extend the reorg/difficulty tests in `tests/test_reorg.py`).

**Verify:** all five scenario reports committed under `reports/attacks/`;
`docs/REORG_RISK_TABLE.md` exists and is referenced by the deposit-policy
code (grep-tested).

## 0.7 Difficulty & hashrate bootstrap  *(community; months)*

**Deliverable:** ≥5 independent miners, no one >30% for 30 days.

- [ ] Ratify `docs/DIFFICULTY_RELAUNCH_PLAN.md` (sign-off line).
- [ ] Publish a one-page miner quickstart on `sites/nodes/`: install →
      `python -m netcoin miner` solo path → Stratum-lite pool path
      (`netcoin/pool.py`; pool tests: `tests/test_p7_stratum_pool.py`).
- [ ] Stand up a public pool instance on one seed; publish its URL + fee.
- [ ] Add hashrate-distribution tracking: node already logs miner addresses
      per block; add a status-site card "blocks by miner, last 1000" and an
      alert when top miner >30%.
- [ ] Write the hashrate-collapse NIP *now* (emergency difficulty epoch
      shortening), so the response to a collapse is a pre-agreed activation,
      not a panic hard fork.
- [ ] Recruit: post in mining communities; track named independent miners in
      `docs/OPERATORS.md`.

**Verify:** status card shows ≥5 distinct sustained miners; 30-day window
with top miner ≤30%.

## 0.8 Genesis & fair distribution  *(days once 0.1–0.2 done)*

- [ ] Ratify `docs/MAINNET_GENESIS_DISTRIBUTION_PROPOSAL.md`: premine amount
      (or zero), founder/treasury allocations with vesting, all disclosed.
- [ ] Final rehearsal: `python tools/generate_genesis.py --network regtest
      --out reports/genesis-rehearsal.json --block-out
      reports/genesis-block.json` (tool hard-refuses mainnet wiring by
      design — `tests/test_p4_genesis_rehearsal.py`).
- [ ] Publish the genesis manifest + manifest hash in
      `docs/M5_LAUNCH_COMMUNICATIONS.md` draft.
- [ ] Get 2 external parties to reproduce the genesis block bit-for-bit from
      the manifest and sign attestations (reuse the wave5 attestation format,
      `tests/test_wave5_2_release_attestations.py`).

**Verify:** 2 independent attestations on file matching your hash.

## 0.9 Node decentralization  *(months, community + eng)*

**Deliverable:** ≥10 independent operators, ≥3 providers, 2 DNS seed domains.

Engineering first — remove the onboarding footguns observed in production:

- [ ] **Advertise self-check** (the exact failure that banned the local seed
      this cycle): before `announce_self()` first fires, node dials its own
      advertised URL (`self_url`) from a fresh connection; if unreachable,
      log a clear error naming the advertise value, skip announcing, set a
      `advertise_unreachable` flag surfaced in `/info` and the webwallet Seed
      tab. Reject RFC1918/loopback/RFC5737 advertise values at argument-parse
      time in `cli.py` with a message explaining public-IP + port-forward
      requirements. Add `tests/test_advertise_self_check.py`.
- [ ] **Seed-tab guidance**: webwallet Seed tab shows "your public IP appears
      to be X (via a peer echo endpoint); you entered Y" mismatch warning.
- [ ] Add a `/peers/echo-addr` endpoint (returns caller's observed IP) to
      support the above without third-party services.
- [ ] Single onboarding page: merge learn's "become a public seed" checklist
      with a systemd unit template + `MemoryMax` override (the exact config
      proven on the three seeds this cycle) into `docs/OPERATOR_RUNBOOK.md`.

Operational:

- [ ] Create `docs/OPERATORS.md` registry: operator name/contact, provider,
      region, node URL, date joined.
- [ ] Migrate the 3 project seeds to ≥2 different providers and upsize RAM
      (1.9GB boxes caused this cycle's OOM incidents; ≥4GB).
- [ ] Stand up DNS seeder #2 under a different operator + domain
      (`netcoin/peerdb.py` + seeder tested in `tests/test_p6_dns_seeder.py`;
      the gap is purely operational).
- [ ] Recruit to 10 operators; publish count + map on status site.

**Verify:** `docs/OPERATORS.md` lists ≥10 with ≥3 providers; `dig` returns
answers from 2 independent seed domains; advertise self-check tests green.

## 0.10 Release integrity chain  *(1 week eng + process)*

- [ ] Release workflow gate: `.github/workflows/release.yml` runs
      `tools/verify_reproducible_build.py` (local vs docker hash compare —
      comparator tested in `tests/test_wave5_3_reproducible_build_ci.py`);
      publish blocked on mismatch.
- [ ] GPG-sign `SHA256SUMS` in the workflow; publish the signing pubkey on
      `sites/download/` and in the repo.
- [ ] Recruit 3 independent verifiers; per release they run the comparator
      and submit signed attestations (planner exists:
      `tests/test_wave5_2_release_attestations.py`); store under
      `attestations/<version>/`.
- [ ] Harden `tools/deploy_seed.sh` (all found-in-production this cycle):
      - [ ] `chmod -R a+rX "$SRC_DIR"` after copy (done locally — commit it)
      - [ ] export `TMPDIR` to a real-disk path before pytest (tmpfs /tmp
            caused a 228-test false failure)
      - [ ] self-copy execution: script copies itself to `mktemp` and
            `exec`s the copy so mid-run source replacement can't change the
            running script (caused the stale-120s-healthcheck rollback)
      - [ ] verify zip signature (`tools/verify_release.py`) before
            extracting; refuse unsigned artifacts
- [ ] Operator docs: verification steps before any deploy
      (`sites/download/verify.html` exists — link from the runbook).

**Verify:** last 3 releases each have ≥3 attestations; deploy of an unsigned
zip refused in a drill.

## Phase 0 exit gate — all boxes required

- [ ] External audit published, 0 open critical/high
- [ ] Spec frozen, CI guard live, one external spec review signed
- [ ] Total-supply test green and published
- [ ] 30 consecutive green fuzz nights, ≥10M cases
- [ ] `docs/REORG_RISK_TABLE.md` published from measured drills
- [ ] ≥10 independent operators, ≥5 miners, 2 DNS seed domains
- [ ] 3 releases verified by ≥3 independent parties each

---

# Phase 1 — Wallet & key security

## 1.1 Hardware wallet support  *(3–6 weeks)*

**Deliverable:** end-to-end send with keys that never touch the computer;
strict evidence gate passes.

- [ ] Define `netcoin/signers/base.py`: `SignerAdapter` interface —
      `get_xpub()`, `display_address(path)`, `sign_psbt(psbt) -> psbt`,
      `sign_challenge(msg) -> sig`. All wallet signing flows route through
      it (software signer becomes adapter #0, keeping tests uniform).
- [ ] Implement adapter #1: **air-gapped QR signer profile** (SeedSigner
      class device or a dedicated offline phone/laptop running the offline
      wallet) — no vendor lead time, proves the interface:
      - [ ] chunked/animated QR encode of unsigned PSBT (wallet UI)
      - [ ] offline device signs (1.2 flow), returns signed PSBT via QR
      - [ ] wallet decodes, combines (`test_psbt_flow.py` combine path),
            broadcasts
- [ ] Implement adapter #2: **HWI-style USB bridge** for Trezor-class
      devices (open firmware; custom-coin support): host-side python-hid
      bridge process, wallet talks to it over localhost with origin checks.
- [ ] On-device verification requirements (both adapters):
      - [ ] receive address rendered on device and confirmed before use
      - [ ] tx outputs + amounts + fee rendered on device before signing
- [ ] Negative tests: signature from wrong device/key rejected; tampered
      PSBT (output swapped after device review) fails verification.
- [ ] Fill the existing strict evidence gate
      (`hardware-wallet-device-testing` in `netcoin/mainnet_readiness.py`,
      required fields per `tests/test_v041_mainnet_readiness.py`): device
      model, firmware, transport, on-device address+tx review booleans,
      challenge signature verified, operator attestation, evidence hash.
      Store at `reports/mainnet_evidence/hardware.json`.

**Verify:** `python tools/check_mainnet_launch_readiness --strict` (the v041
gate) passes for hardware; a real send completes with the signing key
generated on-device.

## 1.2 Air-gapped / offline signing UX  *(1–2 weeks)*

- [ ] Add `--offline` flag to `python -m netcoin web`: disables every
      outbound network call; add `tests/test_offline_mode.py` asserting no
      sockets opened (monkeypatch `socket.socket` to raise).
- [ ] QR round-trip: PSBT → chunked QR frames → decode; unit tests for chunk
      loss/reorder (re-request missing frames).
- [ ] Wallet UI: "Offline signing" tab — export unsigned (file or QR),
      import signed, broadcast; progress states.
- [ ] Two-machine ceremony doc with photos in wallet docs; functional flow
      already pinned by `tests/test_offline_signing_flow_functional.py` and
      the production PSBT round-trip in
      `tests/test_post_m5_engineering_backlog.py`.

**Verify:** complete a send with the signing machine's networking disabled
at OS level; offline-mode socket test green.

## 1.3 Multisig custody UX  *(2–3 weeks)*

- [ ] Wallet UI: create-multisig flow (2-of-3 / 3-of-5): collect cosigner
      xpubs via file/QR, derive + cross-verify receive addresses on all
      cosigners before first use.
- [ ] Spend flow UI: originate → export partial PSBT per cosigner → import
      signatures → progress meter ("2 of 3 collected") → combine → broadcast
      (multiparty combine already tested:
      `tests/test_psbt_flow.py::test_multiparty_combine`).
- [ ] Policy layer: per-wallet rules stored with the wallet (e.g. spends
      >X NET require all N signatures); enforce in the build step; reuse
      `netcoin/wallet_approvals.py` risk queue for held spends.
- [ ] Tests: full 2-of-3 spend across three separate wallet instances;
      policy-violating spend blocked; mismatched-xpub address verification
      failure caught.

**Verify:** scripted 2-of-3 spend end-to-end in
`tests/test_multisig_ux_flow.py`; manual 3-machine drill logged.

## 1.4 Dynamic fee estimation + RBF  *(2 weeks)*

- [ ] Node endpoint `GET /fees/estimate`: mempool feerate histogram by
      weight; return sats/vB for targets {1, 3, 10} blocks + minimum relay
      (extend the existing `mempool-info --summary` machinery).
- [ ] Policy (NOT consensus — keep flags separate per 0.1): BIP125-style
      opt-in RBF:
      - [ ] tx signals replaceability (nSequence < 0xfffffffe)
      - [ ] mempool replacement rules: higher absolute fee AND feerate; no
            new unconfirmed inputs; cap replacement chains
      - [ ] tests: full accept/reject matrix in `tests/test_rbf_policy.py`
- [ ] Wallet: fee selector (fast/normal/economy) wired to the endpoint;
      feerate sanity warning (">5% of send amount"); "Bump fee" button on
      pending sends rebuilding with higher fee (send pre-checks for
      balance/weight already exist — extend).
- [ ] Explorer: render replacement chains (original marked replaced).
- [ ] Congestion drill: use `tools/run_rate_limit_loadtest.py` pattern to
      flood mempool, strand a low-fee send, bump via UI, confirm.

**Verify:** `pytest tests/test_rbf_policy.py` matrix green; scripted
strand-and-bump drill passes.

## 1.5 Backup & recovery, drilled  *(2–3 days + quarterly)*

Core already strong (`tests/test_wallet_safety.py`,
`test_wallet_migration.py`, `test_wallet_cli.py`: AEAD + tamper rejection,
mnemonic recover-test, watch-only export, private file perms, versioned
migration). Remaining:

- [ ] Write `tools/run_recovery_drill.py`: fresh temp dir → install from
      release artifact → recover wallet from mnemonic → compare derived
      addresses/balance vs explorer → emit evidence JSON
      (`reports/mainnet_evidence/recovery-<date>.json`).
- [ ] Schedule quarterly; keep last 4 evidence files in repo.
- [ ] User-facing recovery guide covering actual failure modes (wrong
      passphrase, partial mnemonic, legacy-KDF files) and their exact error
      messages.

**Verify:** two consecutive quarterly drill evidence files present.

## 1.6 Spending controls for end users  *(1 week)*

- [ ] Wallet UI limits panel: per-tx cap, daily cap, address allowlist —
      persisted with the wallet; conservative defaults ON for new wallets.
- [ ] Large-send delay: sends over the cap enter the approval queue
      (`netcoin/wallet_approvals.py` — engine tested) with a 24h hold and a
      one-click cancel; notification on entry.
- [ ] New-allowlist-address 24h delay before first use.
- [ ] Unify enforcement: user limits and the developer funding-policy engine
      (`_enforce_developer_funding_policy` — daily caps/per-user caps/pause,
      shipped + tested in `tests/test_developer_funding_policy.py`) call one
      shared limit-check path.
- [ ] Attack test: `tests/test_spending_controls.py` — simulated
      compromised unlocked session cannot extract more than daily cap;
      cancel-during-delay works; allowlist bypass attempts fail.

## Phase 1 exit gate

- [ ] Hardware evidence gate strict-passes with a real device
- [ ] Offline-mode socket test green + manual air-gap drill logged
- [ ] 2-of-3 multisig spend test green + 3-machine drill logged
- [ ] RBF matrix green + strand-and-bump drill passed
- [ ] Two recovery-drill evidence files
- [ ] Spending-controls attack test green, defaults on

---

# Phase 2 — Exchange engine

Existing seeds: `netcoin/exchange.py` (custody ledger),
`netcoin/exchange_accounting.py` (AccountingLedger),
`netcoin/custody_production.py`, the markets CLOB
(`netcoin/apps/markets/`), push-on-deposit + webhook HMAC/retry/dead-letter
(shipped this cycle), `netcoin/wallet_approvals.py`.

## 2.1 Order book & matching engine  *(3–4 weeks)*

**Build order: 2.2 first — matching writes only ledger postings.**

- [ ] Design doc `docs/exchange/MATCHING_ENGINE.md`: event-sourced core —
      append-only order-event log (place/cancel/fill) in SQLite WAL; book
      state = pure fold; snapshot every N events + replay on restart.
- [ ] Lift, don't rewrite: the markets CLOB already implements limit orders,
      order tickers, orderbook depth, FOK and post-only guards
      (`tests/test_polymarket_style_markets.py`) — extract its matching core
      into `netcoin/exchange_engine.py` parameterized by market
      (outcome-shares vs spot pairs).
- [ ] Matching loop: single-threaded per market; price-time priority;
      atomic partial fills.
- [ ] Order types checklist: limit ☐ market ☐ IOC ☐ FOK ☐ post-only ☐
      (FOK/post-only port from markets).
- [ ] Self-trade prevention (cancel-newest default); per-account open-order
      cap; per-market tick/lot size validation.
- [ ] Determinism harness `tests/test_matching_determinism.py`:
      - [ ] fuzz 10,000 random order events; assert replay(log) ==
            live-state hash
      - [ ] conservation: sum(base fills) and sum(quote fills) balance to
            zero net of fees, every step
      - [ ] kill-and-restart mid-stream loses nothing
- [ ] Circuit breakers (for 2.9): per-market price band vs last trade;
      halt + auction-reopen; tests for band trigger/release.

**Verify:** determinism + conservation + restart tests green at 10k events;
100k-event soak run clean.

## 2.2 Double-entry ledger with enforced invariants  *(2 weeks — FIRST)*

- [ ] Extend `netcoin/exchange_accounting.py`:
      - [ ] `postings` journal table: (posting_id, txn_id, account, asset,
            amount, created_at) — append-only, no UPDATE/DELETE (enforce
            with SQLite triggers)
      - [ ] every `txn_id` group must sum to zero per asset — CHECK at
            write time in the posting API (single code path; no other
            balance writes anywhere in the codebase — add a grep test)
      - [ ] sub-balances: `available` vs `hold` (order holds, withdrawal
            holds) with hold place/release postings
      - [ ] materialized balances table updated only by the posting API
- [ ] Invariant checks on every write: no negative available; user-liability
      total ≤ custody-asset total (custody accounts flagged).
- [ ] Nightly audit job `tools/run_ledger_audit.py`: recompute all balances
      from the journal, diff vs materialized, exit nonzero on any drift;
      wire to cron + alert (3.1).
- [ ] Chaos test `tests/test_ledger_chaos.py`: spawn writer, `kill -9` at
      random points 1,000 iterations, run audit each time — zero drift.

**Verify:** chaos test green ×1000; grep test proves no balance writes
outside the posting API; nightly audit green 30 days.

## 2.3 Deposit pipeline (reorg-safe)  *(2 weeks)*

Foundation shipped: watch-address detection with
`notified_txids`/`last_seen_height` dedupe + `deposit.detected` webhook
(`tests/test_push_on_deposit.py`).

- [ ] Confirmation policy module `netcoin/exchange_deposits.py`:
      `required_confs(amount)` implementing the tier table **derived from
      `docs/REORG_RISK_TABLE.md` (0.6)** — placeholder until measured:
      <10 NET: 6 · <1,000: 20 · ≥1,000: 60. Add a code comment citing the
      table and a grep test that the citation exists.
- [ ] State machine per deposit: `seen → confirming(n/N) → credited` with
      (txid, block_hash, height) recorded at credit time.
- [ ] Reorg reversal:
      - [ ] on tip change, walk credited deposits whose block_hash is no
            longer in the main chain (explorer reorg-watch machinery exists)
      - [ ] move to `reversed`; post claw-back ledger txn (2.2)
      - [ ] if available balance insufficient (already traded/withdrawn):
            freeze account, negative-balance posting, page operator (3.1),
            open fraud case (2.10)
- [ ] Per-user unique deposit addresses (wallet address-rotation counter
      exists — `tests/test_remaining_code_upgrades.py` pins persistence);
      sweep credited deposits to custody per 2.5 schedule.
- [ ] Drill `tools/run_deposit_reorg_drill.py`: on the 0.6 harness, orphan
      credited deposits at every pipeline stage ×100 runs; assert ledger
      audit green and no unaccounted credits after each.

**Verify:** reorg drill 100/100 clean; state-machine unit tests cover every
transition including reversal-after-withdrawal freeze.

## 2.4 Withdrawal pipeline (tiered)  *(2–3 weeks)*

Building blocks: withdrawal records in `exchange.py`, risk-scored approval
queue (`wallet_approvals.py`), payout signing-policy attachment
(`tests/test_phase7_hardening.py`), manual signing default (checklist).

- [ ] Tier config: `auto` (≤X NET, hot wallet, post-risk-screen) /
      `operator` (≤Y, one approver) / `cold` (>Y, 1.3 multisig ceremony).
      X/Y set conservatively at launch (see Phase 6 step 8).
- [ ] Pipeline state machine: `requested → screened → approved(tier) →
      signing → broadcast → confirming → complete | rejected | cancelled` —
      every transition audit-logged with actor.
- [ ] Ledger integration: hold posted at request; released at broadcast-
      confirmed or cancel; crash at any state leaves hold consistent
      (extend `tests/test_ledger_chaos.py` scenarios).
- [ ] Risk screen (pre-approval, feeds 2.10):
      - [ ] velocity vs account history
      - [ ] new-address 24h delay + allowlist check
      - [ ] deposit-then-immediate-withdraw pattern hold
- [ ] Broadcast: idempotent (txid recorded before send; re-broadcast safe);
      stuck-tx fee bump via 1.4 RBF.
- [ ] End-to-end tests per tier in `tests/test_withdrawal_pipeline.py`,
      including kill-process chaos at each state.

**Verify:** all three tier flows green; chaos leaves holds consistent;
audit log complete for every test run.

## 2.5 Hot/cold custody split  *(2 weeks + ceremony)*

- [ ] Cold key ceremony per `docs/MAINNET_COLD_STORAGE_RUNBOOK.md`:
      hardware-generated (1.1) multisig quorum (1.3), witnessed, documented;
      quorum devices geographically separated; record as custody evidence
      (`custody_approval` is one of the seven strict launch approvals in
      `tools/check_mainnet_launch_approval.py`).
- [ ] Sweep job: hot balance > threshold → build sweep tx to cold; runs on
      schedule; alert (not auto-fix) on failure.
- [ ] Replenishment: cold→hot is a manual dual-control ceremony only;
      documented; every execution logged with both approvers.
- [ ] Alarms: hot share >5% (risk) or < withdrawal-demand floor (stall).
- [ ] Monthly reconciliation: on-chain custody balances vs ledger custody
      accounts (feeds 2.6).

**Verify:** 30 days with hot ≤5% and zero out-of-ceremony cold movements;
ceremony evidence on file.

## 2.6 Proof of reserves & liabilities  *(1–2 weeks)*

- [ ] `tools/generate_reserve_proof.py`:
      - [ ] snapshot ledger at height H → Merkle-sum tree of (salted user
            ID, balance); publish root + total liabilities
      - [ ] per-custody-address challenge signature at the same H (proves
            key control) → publish with address list
- [ ] User verification endpoint + wallet-side verifier: user fetches their
      inclusion proof, verifies leaf → root and balance-sum monotonicity.
- [ ] `tests/test_reserve_proof.py`: inclusion proofs verify; tampered leaf
      fails; liabilities ≤ reserves asserted; a v1 reserves endpoint already
      exists in `exchange.py` (`test_upgrade_batches.py` batch 4) — extend,
      don't fork.
- [ ] Publish monthly (even in paper mode, per Phase 6 step 3); archive all
      historical proofs; publish an honest limitations note (point-in-time;
      can't prove absence of off-book liabilities).

**Verify:** an external user verifies their own inclusion + the total using
only published data.

## 2.7 Fiat rails  *(4–6 weeks after Phase 4.6 — hard-gated)*

- [ ] **Gate: signed banking/PSP agreement (4.6). No code path around it.**
- [ ] Integrate PSP deposit webhooks → ledger postings (reuse the webhook
      HMAC verify/retry/dead-letter machinery —
      `tests/test_webhook_dead_letters.py`, `verifyNetcoinWebhook` in the
      SDK).
- [ ] Withdrawal batches to the PSP with the same tiering as 2.4.
- [ ] Daily reconciliation `tools/run_fiat_recon.py`: bank statement vs
      ledger fiat account; any break freezes fiat ops + pages.
- [ ] Interim option (decide explicitly): crypto-only launch (NET↔BTC/USDC)
      — still requires most of Phase 4, not the bank.

**Verify:** 30 consecutive daily recons, zero unresolved breaks.

## 2.8 Market data & trading APIs  *(2–3 weeks)*

Foundations: `/v1` aliases + OpenAPI checker
(`tests/test_p9_api_v1_openapi_sdk.py`), per-key rate limits with
Retry-After (`tests/test_p8_node_installer_rate_limit.py`), markets
ticker/orderbook endpoints, JS/Python SDKs, `sdk/netcoin-developer`.

- [ ] REST: `GET /v1/exchange/{ticker,depth,trades,candles}`; private:
      order place/cancel, balances, history — all in `docs/openapi.yaml`
      (spec checker will enforce).
- [ ] Auth: API keys with scopes (read/trade/withdraw — withdraw scope
      requires explicit enable + allowlist); HMAC request signing with
      timestamp window (reuse webhook HMAC pattern).
- [ ] Candle aggregation job from the 2.1 fill log (1m base, roll-ups).
- [ ] WebSocket sidecar (stdlib HTTP node can't hold WS): small async
      service consuming the event log; channels: trades, depth deltas,
      user orders; sequence numbers + resync protocol.
- [ ] SDK: add trading calls to `sdk/netcoin-developer` + Python SDK;
      round-trip test per endpoint.
- [ ] Load: 10× expected volume via the loadtest tool pattern; WS
      reconnect/replay correctness test.

**Verify:** OpenAPI checker green; SDK round-trips green; loadtest report
committed.

## 2.9 Liquidity bootstrap  *(2 weeks eng + capital)*

- [ ] MM bot in `bots/market_maker/` on the 2.8 API: configurable spread,
      inventory bands, kill switch; runs in paper mode first.
- [ ] Published MM program terms (spread/uptime obligations ↔ fee rebates)
      if external MMs join.
- [ ] Circuit breakers live (built in 2.1) with published band parameters.
- [ ] Listing-criteria doc for any future pair.

**Verify:** 30 days paper-mode with median spread under target; kill switch
drill executed.

## 2.10 Fraud, risk & market surveillance  *(3 weeks)*

- [ ] Rule engine `netcoin/exchange_risk.py` (pattern from
      `wallet_approvals.py` risk scoring): every rule fire logged (rule id,
      score, action).
      Account rules: ☐ velocity ☐ deposit-trade-withdraw fast cycle
      ☐ many-accounts-one-device ☐ credential-stuffing (failed-login
      clustering).
- [ ] Surveillance jobs over the 2.1 event log (deterministic = replayable):
      ☐ self-match/wash detection ☐ spoofing (high cancel-to-trade near
      touch) ☐ layering ☐ momentum-ignition pattern.
- [ ] Review queue UI on the operator site (natural home — operator
      dashboard exists): case states open → investigating →
      resolved(action); full audit trail. This queue is also the AML
      transaction-monitoring substrate for 4.5.
- [ ] Red-team scripts `tools/run_fraud_redteam.py`: execute wash trade,
      spoof pattern, rapid deposit-withdraw — each must trigger its rule
      and land a case.

**Verify:** red-team run: 100% intended rules fire; zero silent passes.

## Phase 2 exit gate

- [ ] Ledger chaos ×1000 zero-drift; nightly audit green 30 days
- [ ] Matching determinism + conservation green at 100k events
- [ ] Deposit reorg drill 100/100; withdrawal tier flows + chaos green
- [ ] Hot ≤5% for 30 days; cold ceremony evidence filed
- [ ] Reserve proof externally verified; published twice
- [ ] API loadtest at 10×; SDK round-trips green
- [ ] Red-team fraud scripts 100% detected
- [ ] 90 days paper-mode operation logged (Phase 6 step 3)

---

# Phase 3 — Operations at financial grade

## 3.1 Monitoring & paging  *(1 week eng + staffing)*

Base: Prometheus metrics + Grafana dashboard (tested in
`tests/test_p12_explorer_faucet_status_metrics.py`), status-site uptime
history, ops diagnostic bundles with secret redaction
(`netcoin/ops_runbooks.py`).

- [ ] Deploy Alertmanager + paging service (PagerDuty/Opsgenie).
- [ ] Alert catalog `docs/operations/ALERT_CATALOG.md` — one row per alert:
      condition, severity, page-or-ticket, runbook link (the
      `recommended_actions` mapping in ops_runbooks is the seed).
      Required alerts:
      ☐ chain halt (no block > N min) ☐ reorg depth > policy
      ☐ ledger audit drift ☐ withdrawal queue age > SLA
      ☐ hot-wallet out of band ☐ node/seed down ☐ cert expiry <14d
      ☐ `/debug/memory` RSS trend (endpoint shipped this cycle)
      ☐ fuzz nightly red ☐ fiat recon break
- [ ] Synthetic failure drill per alert class → page received <5 min;
      log results.
- [ ] On-call rotation: requires ≥2 humans. If solo, document the coverage
      gap explicitly in the risk register — partners in Phase 4 will ask.

## 3.2 Incident response, practiced  *(ongoing)*

`docs/INCIDENT_RESPONSE.md` exists and is test-pinned. Add:

- [ ] Money-specific runbooks: ☐ wrong payout claw-back ☐ key compromise
      (freeze authority + dual control) ☐ deposit-reorg fraud ☐ data breach
      notification steps.
- [ ] Write up this cycle's three real incidents as case studies (OOM
      crash-loop → MemoryMax; SQLite corruption → self-heal; deploy
      rollback race → script fixes) — they are the drill material.
- [ ] Quarterly tabletop: pick one runbook, execute on staging, record
      evidence JSON; two on file before launch.

## 3.3 Backups & disaster recovery  *(1 week)*

- [ ] Automate the manual path proven this cycle: hourly WAL-aware SQLite
      backups via the Python `.backup()` API (used on seed3 when the sqlite3
      CLI was absent) for: chain DB, app store, peer DB → encrypted →
      off-site bucket. This is the "Layer 3" cron proposed and not yet
      built.
- [ ] Ledger journal (2.2): ≤5-min snapshot cadence or streaming replication
      — RPO 5 min. Everything else: RPO 1h. RTO: 4h to warm standby.
- [ ] Warm standby in a second region: restore-from-backup bootstrap script.
- [ ] Quarterly timed restore drill into a clean VM
      (`tools/run_restore_drill.py`, evidence JSON); two on file.
- [ ] Chain self-heal already shipped (`chain.py::load_or_create` recovery,
      `tests/test_chain_self_heal.py`) — covers corruption; this item covers
      box/region loss.

## 3.4 Infrastructure hardening  *(2 weeks + recurring cost)*

- [ ] CDN/WAF (Cloudflare-class) in front of every public surface; origin
      IPs locked to CDN ranges.
- [ ] Replace 1.9GB seed instances (≥4GB — root cause of this cycle's OOM
      incidents); keep systemd `MemoryMax` + `Restart=always` as
      defense-in-depth (already on all 3 seeds).
- [ ] Secrets to a manager (KMS/SSM): `NETCOIN_APP_ADMIN_TOKEN`, API keys,
      webhook secrets, GPG release key; rotation schedule; ops-bundle
      redaction already tested — add a log-scan job asserting no secrets in
      logs.
- [ ] SSH: bastion-only, hardware-key auth, no password auth; per-operator
      keys (no shared `final-aws-key.pem`).
- [ ] Enforce `docs/NGINX_SECURITY_HEADERS.md` with a header-check script in
      CI against staging.
- [ ] Land the deploy-script hardening (0.10 checklist) in `main`.
- [ ] External infra pentest (separate scope from the 0.3 code audit);
      findings into the 0.4 register.

## 3.5 Operator access control  *(1–2 weeks)*

- [ ] Roles: viewer / operator / approver / root; per-role credentials
      (admin-token gating exists — `NETCOIN_APP_REQUIRE_ADMIN`, tested;
      faucet admin audit is the logging pattern).
- [ ] Hardware-key 2FA for every operator account.
- [ ] Dual control: custody actions (2.5 ceremonies, cold-tier withdrawals,
      account freezes) require two distinct approver credentials — enforced
      in code, tested.
- [ ] Admin audit log: append-only, hash-chained, in backups;
      `tools/verify_admin_log_chain.py` in CI.

## 3.6 Change management  *(process)*

- [ ] Staging environment mirroring prod topology (can be small instances).
- [ ] Canary rule codified: seed3 first (matches this cycle's de facto
      canary-then-fleet process), soak 24h, then fleet.
- [ ] `docs/M5_LAUNCH_FREEZE_POLICY.md` invoked for launch windows;
      rehearse once.
- [ ] Post-deploy verification: deploy script's test+healthcheck+rollback
      (kept hardened per 0.10) + smoke check
      (`tools/check_m1_live_smoke.py` pattern) against the deployed fleet.

## Phase 3 exit gate

- [ ] Every alert class drill-paged <5 min; catalog complete
- [ ] Two tabletop evidence files; money runbooks written
- [ ] Two timed restore drills meeting RPO/RTO
- [ ] Infra pentest: no open high findings
- [ ] Dual-control enforced + tested; admin log chain verifies
- [ ] Canary + freeze rehearsed

---

# Phase 4 — Legal & regulatory (professionals required; hard blocker)

Cannot be built in this repo. Checklist tracks engagement state, not code.

## 4.1 Entity & governance
- [ ] Engage fintech counsel (before anything else — structure decisions
      cascade)
- [ ] Form entity/entities (often: token/foundation separate from exchange
      opco); board; registered agent
- [ ] Appoint named compliance officer (license prerequisite in most regimes)

## 4.2 Securities / token classification
- [ ] Written Howey analysis for NET + every distribution channel (mining
      cleanest; any sale/premine raises risk; developer-rewards program —
      the funding-policy engine's records are your evidence trail)
- [ ] EU MiCA classification memo if EEA users contemplated
- [ ] **Deliverable: legal opinion letter** shareable with banks/partners

## 4.3 FinCEN MSB registration (US)
- [ ] Register (weeks, low cost); calendar the renewal
- [ ] Understand it commits you to 4.5 obligations permanently

## 4.4 Money transmission authorization — pick a path with counsel
- [ ] Path A: US state-by-state MTLs (12–24 months, $0.5M–$2M+ incl. bonds)
- [ ] Path B: EU MiCA CASP authorization (single passportable license —
      often the tractable first jurisdiction)
- [ ] Path C: partner with a licensed custodian/CaaS provider (fastest,
      fee-heavy, still needs 4.2/4.5)
- [ ] Decision memo signed; application filed; tracker for examiner Q&A

## 4.5 KYC/AML program
- [ ] Written AML program + named officer
- [ ] IDV vendor integrated (Persona/Jumio class) — registration flow
- [ ] Sanctions/OFAC screening at onboarding + ongoing re-screen
- [ ] Transaction monitoring: 2.10's engine + documented thresholds; SAR
      filing procedure
- [ ] Travel Rule solution for transfers above threshold
- [ ] 5-year record retention design (interacts with 4.8 privacy — decide
      retention schedule once)
- [ ] Annual independent AML audit scheduled

## 4.6 Banking partner
- [ ] Pitch package: audit report (0.3), proof of reserves (2.6), compliance
      program (4.5), entity docs (4.1) — this plan is the data room
- [ ] Primary bank or PSP/BaaS signed; backup relationship established

## 4.7 Tax reporting
- [ ] 1099-DA (US) / DAC8 (EU) capability: ledger (2.2) stores cost-basis
      lots per user
- [ ] Year-end reporting pipeline tested against sample data

## 4.8 Terms, privacy, data protection
- [ ] ToS (custody terms, fork/airdrop policy, dispute resolution)
- [ ] Privacy policy; GDPR/CCPA data-subject-request procedure that actually
      works against your logs/ledger (test it once)

## 4.9 Insurance
- [ ] Crime/specie quote for hot wallet; bind at launch limits
- [ ] D&O for the entity; any license-mandated bonds

## Phase 4 exit gate
- [ ] Securities opinion letter on file
- [ ] Entity + compliance officer in place
- [ ] One jurisdiction fully authorized (A, B, or C path complete)
- [ ] KYC/AML live end-to-end with vendor (test onboarding passes)
- [ ] Banking/PSP agreement signed; recon tested (2.7)
- [ ] Insurance bound

---

# Phase 5 — Market credibility

- [ ] **5.1** Miner/node distribution stats live on status site (0.7/0.9
      instrumentation)
- [ ] **5.2** Audit report published on `sites/security/`; bug bounty
      (`sites/security/bug-bounty.html` exists) funded with real amounts;
      payout history public
- [ ] **5.3** Treasury addresses published (governance site treasury anchor
      exists); monthly spend report; reuse 2.6 proof tooling
- [ ] **5.4** Listing data room assembled (= this plan's artifacts);
      CoinGecko/CMC supply API endpoint; approach listing venues
- [ ] **5.5** Merchant adoption measured: weekly active payment volume via
      the pay/hosted-checkout + merchant + SDK stack (shipped this cycle);
      publish the metric
- [ ] **5.6** Comms discipline: `docs/M5_LAUNCH_COMMUNICATIONS.md` final;
      never claim beyond the evidence gates (the "does not claim mainnet
      readiness" test-enforced strings stay until they're true)

---

# Phase 6 — Launch sequence (each step gated by the previous)

1. - [ ] **Phase 0 exit gate all green** (audit, spec, fuzz, reorg table,
         decentralization, releases)
2. - [ ] **Phase 1 exit gate all green** (hardware, air-gap, multisig, RBF,
         recovery, limits)
3. - [ ] **Paper mode, 90 days:** Phase 2 stack on final testnet; synthetic
         + volunteer traffic; weekly chaos/reorg drills
         (`tools/run_deposit_reorg_drill.py`, attack drills); monthly
         reserve proofs published as practice; all incidents postmortemed
4. - [ ] **Phase 3 exit gate all green** (paging, DR, pentest, dual
         control)
5. - [ ] **Phase 4 exit gate all green** in launch jurisdiction(s) —
         no partial credit
6. - [ ] **Strict launch gate:** `python tools/check_mainnet_launch_approval.py
         --strict` passes — all seven evidence approvals present (release
         manager, security, ops, wallet, custody, rollback plan,
         genesis/upgrade hash); machinery already built and tested
         (`netcoin/mainnet_readiness.py`,
         `tests/test_v041_mainnet_readiness.py`)
7. - [ ] **Mainnet genesis** per `docs/M5_MAINNET_LAUNCH_RUNBOOK.md`;
         ≥2 external genesis-hash verifications (0.8); freeze policy active;
         post-launch monitoring per `docs/M5_POST_LAUNCH_MONITORING.md`
8. - [ ] **Custody-only open, 30 days:** deposits/withdrawals only, no
         trading; conservative tier limits (e.g. auto ≤10 NET, operator
         ≤100, cold above); daily ledger audit + recon reviewed by a human
9. - [ ] **Trading opens:** one pair; MM live (2.9); circuit breakers on;
         surveillance queue staffed; reserve proof from real custody
         published in week 1
10. - [ ] **Scale by evidence:** limits/pairs raised only after
          incident-free intervals; standing quarterly cadence: reserve
          proof, restore drill, tabletop, AML review, register check
          (`tools/check_findings_register.py`)

**Rollback doctrine:** before starting any step, write its rollback into the
step's evidence file (the launch gate literally requires `rollback_plan`).
If a rollback would be ambiguous, the step is not ready.

---

# Cross-cutting: critical path, budget, staffing

**Critical path:** 0.3 (audit booking lead) and Phase 4 (12–24 months)
dominate — **start both engagements first**, run Phases 1–3 engineering in
parallel while they proceed.

**Budget floor (ex-salaries):** audit $50–150k · infra pentest $20–40k ·
legal/licensing $250k–$2M+ (path-dependent) · KYC vendor + compliance
tooling $50k+/yr · insurance variable · MM capital + bounty fund + infra
upsize. Realistic pre-first-trade total: **high six to seven figures.**

**Minimum launch team:** 2+ engineers (on-call coverage), 1 compliance
officer, 1 ops/support, counsel on retainer. Solo operation is a disclosed
risk every partner (bank, insurer, listing venue) independently rejects.

## Start-today list (no legal blocker; ordered; each is a self-contained PR)

1. - [ ] **1.4 RBF + dynamic fees** — biggest everyday-UX gap (2 weeks)
2. - [ ] **0.5 nightly-fuzz workflow** — tooling exists, wire the YAML (days)
3. - [ ] **2.2 ledger invariants** — everything in Phase 2 stands on it
         (2 weeks)
4. - [ ] **2.3 reorg-safe deposit reversal** — extends this cycle's
         push-on-deposit (2 weeks)
5. - [ ] **1.1 signer interface + air-gapped QR profile** — weakest custody
         rating (3 weeks)
6. - [ ] **2.6 proof-of-reserves Merkle tool** — trust feature even on
         testnet (1–2 weeks)
7. - [ ] **0.9 advertise self-check + operator runbook** — fixes the exact
         footgun that banned the local seed this cycle (3 days)
8. - [ ] **0.3 send the audit scoping package for quotes** — calendar lead
         time is the point (1 day to send)
