# Code-to-Eight Plan — every code feature to ≥8/10

Baseline: `a7a1521` (full suite 752/0, coverage 75.58%, CI green).
Scope: **code-related features only.** Governance, legal, liquidity, and
physical-evidence items are out of scope here (tracked in the milestone plans).

## The contract: what "8" means

An 8 requires ALL of:

1. **Complete behavior** — no TODO paths, no "guidance copy" standing in for function.
2. **Adversarial tests** — not just happy-path: malformed input, hostile peers,
   resource exhaustion, concurrency.
3. **Real-world validation** — exercised against the live public testnet (or a
   real multi-node network), not only unit fixtures.
4. **Observability** — the feature reports its own health (metrics/status/logs).
5. **Documented** — a spec or operator doc an outsider could use.

A feature that cannot obtain #3 from a keyboard has a stated ceiling below.

## Honest ceilings (cannot reach 8 by code alone)

| Feature | Ceiling | Why | What code CAN do |
|---|---|---|---|
| Hardware wallet | 5 | Needs physical Ledger/Trezor transcript | Full WebUSB/WebHID bridge + emulator tests |
| Faucet CAPTCHA | 7 | Needs real provider secrets in prod | Complete adapter + failure modes + load tests |
| versionbits (mainnet) | n/a | Governance-gated (NIP) | Testnet rehearsal to full completion |
| Genesis (mainnet) | n/a | Governance-gated | Testnet/regtest generator + ceremony rehearsal |
| Consensus rules | 7 | 8+ implies external audit | Spec + differential fuzz + benchmarks = audit-ready |
| DNS seeds | 6 | Independent domains/operators are ops | Working seeder daemon serving live peer records |
| SDK publication | 7 | Registry accounts are user-owned | Publish-ready artifacts + CI publish workflow |

Everything else below is keyboard-reachable to 8.

---

## Wave 1 — Verification infrastructure (the multiplier)

"Real-world validation" must be repeatable or every 8 decays. Build once, every
feature benefits. **Do this wave first.**

### 1.1 Multi-node integration harness (new: `tools/run_localnet.py` + tests)
- Spin N (3–7) real `netcoin node` processes on localhost ports with distinct
  data dirs, cross-peered; SQLite backend; mine on node A; assert convergence.
- Assertions: header sync, block relay latency, tx relay, PEX propagation,
  compact-block reconstruction, reorg resolution when two nodes mine competing
  blocks, restart-replay (kill -9 a node, restart, resync).
- Marked `@pytest.mark.localnet`, run in CI as its own lane (or nightly).
- **Unblocks 8s for:** node relay, PEX, AddrV2, compact blocks, fork choice,
  bandwidth, mining pool, DNS seeder.

### 1.2 Live-testnet smoke lane (extend `tools/check_m1_live_smoke.py`)
- Nightly GitHub Action hitting the real seeds (18.220.89.128 + Host headers):
  /info, /supply, /emission, /fee-estimates, /p2p-hardening, explorer pages,
  faucet status, wallet HTML SRI match vs repo.
- Writes `reports/live_smoke_history/<date>.json` (append-only history).
- **Unblocks the "runs in production" half of 8 for every API/site feature.**

### 1.3 Nightly fuzz accumulator (CI)
- Nightly job: `netcoin fuzz --iterations 2_000_000 --out` + upload artifact;
  a small tool sums historical totals toward the 100M evidence file.
- Add **differential fuzz**: same random tx/block dicts fed to Python parser
  AND Rust parity binary; any accept/reject disagreement = consensus bug found
  early. This is the single highest-value security test we can build.

### 1.4 Chaos drill script (`tools/run_chaos_drill.py`)
- Against localnet (never prod without flag): kill nodes mid-sync, corrupt a
  mempool file, partition peers, clock skew. Assert recovery invariants.
- Exercises the incident runbook programmatically → runbook to 8.

**Wave-1 effort:** ~3–4 focused sessions. Highest leverage in the plan.

---## Wave 2 — Consensus & protocol to audit-ready 7 (their max)

| Feature | Now | Work |
|---|---|---|
| Protocol spec | 2 | Write `docs/spec/` — block format, tx format, sighash, scripts/opcodes, address encoding, fork choice, difficulty, emission, mempool policy, P2P messages. Every rule cross-referenced to code + a parity vector. This is also the audit scope packet. |
| Consensus rules | 6 | Expand parity vectors 163 → 300+ (fee edge cases, max-size blocks, locktime/sequence corners, duplicate-txid rule, sigop limits). Differential fuzz (1.3). Performance benchmark tool: block-validation latency P50/P99, restart replay time, memory ceiling — recorded to `reports/perf/`, with regression thresholds in CI. |
| Fork choice | 5 | Localnet contested-mining test (1.1); deep-reorg property tests (random fork points, N-deep); explicit reorg-depth safety doc. |
| Mempool | 5 | Adversarial suite: RBF cycling, pinning, orphan flooding, eviction under cap, fee-sniping shapes. Cross-check against Rust mempool crate verdicts. |
| Emission | 6 | Property tests (monotone non-increasing, cap convergence, integer safety at epoch boundaries ×100 epochs) + spec section. Done → 8. |
| versionbits | 2 | **Testnet-only wiring** behind `NETCOIN_TESTNET_DEPLOYMENTS` config: read real block version bits, drive the state machine, enforce nothing until ACTIVE, then enforce a trivial rehearsal rule (e.g. reject version<X). Run a full rehearsal on localnet, then (with user sign-off) on public testnet seeds. Mainnet stays unwired. → 8 as *testnet rehearsal feature*. |
| Genesis generator | 1 | `tools/generate_genesis.py --network regtest|testnet-rehearsal` — builds + mines block 0 from a validated manifest; **hard-refuses `mainnet`**. Ceremony rehearsal script + docs. → 7 (mainnet ceiling is governance). |

**Effort:** ~4–5 sessions (spec doc is the long pole; do it incrementally).

---

## Wave 3 — Wallet to 8

| Feature | Now | Work |
|---|---|---|
| Offline PSBT | 5 | Wallet UI: Export-unsigned (file + **animated QR for airgap**), Import-signed (file/paste/QR-scan), review screen reusing send-review. Playwright E2E for the full loop. SRI/cache-bust discipline. |
| RBF/CPFP | 4 | Wire helpers to UI: "Speed up" on pending tx (RBF) and on incoming unconfirmed (CPFP). Node mempool must accept replacements (verify + tests). E2E on localnet. |
| Watch-only/xpub | 3 | Real account-xpub export; descriptor import creating tracked addresses; balance/history for watch-only in UI; spend blocked with clear message. |
| Multisig | 3 | Primitives exist (PSBT combine, multiparty tests). Build the flow: create 2-of-3 (collect 3 xpubs → P2SH/P2WSH address), fund, spend via PSBT pass-around using the offline UI. Localnet E2E of a real 2-of-3 spend. |
| Vault | 6 | KDF upgrade path (scrypt/argon2 param bump w/ transparent migration), zeroize key material on lock, vault-format downgrade-attack test, documented brute-force cost table. |
| Send/receive/fees/labels/auto-lock/addr-types | 5–6 | One consolidated adversarial+E2E pass: malformed inputs, node-down mid-send retry-idempotency, fee floor/ceiling, label persistence across restore. Nightly live-testnet E2E (1.2 hooks). |
| Hardware bridge | 2 | Full WebUSB/WebHID transport code + protocol framing + a software device-emulator test double. **Ceiling 5** until physical transcript. |

**Effort:** ~4–5 sessions. Multisig+PSBT-UI is the flagship (it's also a real
competitive feature — see Part B).

---

## Wave 4 — Network/P2P to 8

| Feature | Now | Work |
|---|---|---|
| Node relay | 5 | Localnet suite (1.1) + hostile soak actually run in CI weekly (`tools/run_p2p_soak.py` exists — wire it to localnet + a report artifact). Connection-churn and slow-loris tests. |
| Bandwidth modes | 4 | Today it caps peer counts; add **actual byte-rate enforcement**: token-bucket on socket writes in p2p server + relay scheduler honoring `max_bytes_per_second`. Measured test: home mode sustains <500KB/s under flood on localnet. |
| PEX/AddrV2/compact | 5 | Propagation proofs on localnet: node C learns node A only via B's PEX; compact-block reconstruction with missing txs round-trip. |
| DNS seeder | 2 | New `netcoin seeder` daemon: answers DNS A queries from the live peer DB (stdlib UDP DNS responder), TTL rotation, health-filtered. Localnet test with a real DNS query. **Software 8; ops ceiling 6 until independent domains.** |
| Mining pool | 3 | Make stratum-lite real: getwork/submit over TCP, share validation, per-miner accounting, payout tx construction. Localnet: CPU-mine a block through the pool. |
| Node installer | 3 | CI job that actually runs `docker compose up` (compose file exists) on a GitHub runner, waits for /info, mines a block, tears down. Uninstall + upgrade scripts with tests. |
| Rate limiting | 4 | Token-bucket per key+IP with burst; 429 + Retry-After; loadtest script proving limits hold. |

**Effort:** ~4 sessions (byte-rate enforcement and pool are the meaty ones).

---

## Wave 5 — Supply-chain trust to 8 (mostly CI, big wins available)

| Feature | Now | Work |
|---|---|---|
| Signed releases | 2 | **cosign keyless via GitHub OIDC** — no key ceremony needed; CI signs release artifacts, verification instructions on sites/keys. This legitimately reaches 7–8 *without* the offline-key ceremony (which remains for the strict M2 gate). |
| SLSA provenance | 3 | GitHub's native `actions/attest-build-provenance` on the release workflow = real hosted-builder L2/L3 provenance, replacing our self-generated JSON. |
| Reproducible build | 3 | Run `Dockerfile.repro` in CI and diff against the local digest — a GitHub runner IS an independent second environment. Publishes `reports/m2_evidence/independent_repro_build.json` honestly. |
| SBOM | 4 | Extend generator to include dependency inventory (pip freeze, package-lock, Cargo.lock) as CycloneDX components; attach to releases. |
| Fuzz evidence | 4 | Wave 1.3 accumulator → the 100M report becomes real over ~2 months of nightlies. |
| Incident runbook | 4 | Chaos drill (1.4) + one scheduled game-day against localnet with a written postmortem. |
| Threat model | 3 | Rewrite as per-component STRIDE with explicit consensus-attack section; cross-link spec. |

**Effort:** ~2–3 sessions. Best ROI in the whole plan — several 2s/3s jump to
7–8 using GitHub-native machinery.

---

## Wave 6 — API/SDK to 8

| Feature | Now | Work |
|---|---|---|
| Node API | 6 | `/v1/` versioned aliases + deprecation headers; complete OpenAPI for ALL routes (some node routes undocumented); consistent pagination + error envelope; contract tests generated from the spec. |
| JS/Python SDK | 4 | Real test suites for the SDKs themselves (against localnet); typed TS build for JS SDK; examples dir; CI publish workflow (dry-run until user adds tokens). |
| Rust SDK | 1 | New `sdk/netcoin-rs` crate wrapping the API (client + envelope signing), published-ready. |
| API auth | 5 | Key scopes (read/write/admin), rotation endpoint, HMAC envelope enforcement tests, brute-force lockout. |
| Supply/emission | 5 | Live-smoke coverage (1.2) + spec section → 8. |

**Effort:** ~2–3 sessions.

---

## Wave 7 — Product surfaces to 8

| Feature | Now | Work |
|---|---|---|
| Explorer | 4–5 | Address pagination + CSV export wired to real endpoints; reorg/orphan visual states driven by real events (SSE exists); load test 100 rps on localnet; Esplora-compat layer (Part B). |
| Faucet | 5 | PoW challenge difficulty auto-scaling; drain-attack simulation test; admin audit log; complete CAPTCHA adapter failure modes (ceiling 7 until secrets). |
| Markets | 3 | Real server-side settlement: stake escrow on-chain (app layer), admin-attested oracle resolution, payout txs, dispute window state machine + tests. Honest scope: admin-oracle, not decentralized. |
| Status page | 4 | Uptime history (from 1.2 history), incident banner wired to a repo file, per-seed detail. |
| /metrics | exists | Promote to documented Prometheus format + Grafana dashboard JSON in ops/. |

**Effort:** ~3 sessions (markets settlement is the big one).

---

## Sequencing & totals

```
Wave 1 (verification infra)   ████ 3–4 sessions   ← do first, multiplies everything
Wave 5 (supply-chain trust)   ███ 2–3 sessions    ← cheap 2→8 jumps, do second
Wave 2 (consensus/spec)       ████ 4–5 sessions
Wave 3 (wallet)               ████ 4–5 sessions
Wave 4 (network)              ████ 4 sessions
Wave 6 (api/sdk)              ███ 2–3 sessions
Wave 7 (product)              ███ 3 sessions
                              ─────────────────
                              ~22–27 focused sessions
```

Rules that hold for every wave: full suite green before merge; SRI/cache-bust
discipline on any wallet JS; no consensus change without spec+vectors+parity;
no evidence fabrication; Bucket 3 mainnet paths stay unwired.

---

# Part B — New features that would make NetCoin more competitive

Positioning (per M7 plan): **developer-first Bitcoin-family sandbox.** Judge
every candidate by "does this make a developer choose NetCoin to build/test
against?" Ordered by leverage:

## Tier A — do these (high leverage, moderate cost)

1. **Esplora-compatible API layer** (`/esplora/*` mapping to our data).
   Blockstream's Esplora API is the de-facto standard consumed by BDK, many
   wallets, and countless scripts. Compatibility = existing Bitcoin tooling
   points at NetCoin with a URL change. Single biggest ecosystem unlock
   available. (~1–2 sessions)
2. **Instant local devnet, hardhat/anvil-style.** `netcoin devnet --funded 10`
   → chain with instant blocks, 10 pre-funded wallets printed, `--mine-on-tx`
   auto-mining mode, deterministic seed. Plus a prebuilt Docker image with a
   populated chain for CI fixtures. This is the core dev-sandbox experience.
   (~1 session; devnet base exists)
3. **Programmatic faucet** — faucet claims via API key with per-key quotas, so
   CI pipelines can fund test wallets automatically. No other testnet makes
   this pleasant. (~0.5 session)
4. **Event webhooks + WebSocket** — subscribe to address/tx/block events
   (SSE exists; add WS + signed webhook callbacks with retry). What BlockCypher
   charges for. (~1–2 sessions)
5. **Airgap QR PSBT** (already in Wave 3) — doubles as a competitive wallet
   feature matching modern Bitcoin wallets (SeedSigner-style workflows).

## Tier B — strong candidates after Tier A

6. **Electrum-protocol subset server** — unlocks Electrum-class wallets and
   libraries; bigger lift than Esplora layer. (~3 sessions)
7. **Chain-analytics transparency endpoints** — supply distribution, top
   holders, coin-age; feeds the trust story and gives dashboards something to
   show. (~1 session)
8. **Testnet snapshot/restore** — operators bootstrap a node from a signed
   snapshot in minutes instead of syncing; also our own seed-recovery story.
   (~1 session)
9. **`netcoin-testkit` (pytest/vitest plugin)** — fixtures that spin a devnet
   per test module; makes third-party projects test against NetCoin trivially.
   (~1 session)

## Tier C — noted, deliberately deferred

- **Payment channels / Lightning-like L2** — wrong stage; revisit at real usage.
- **Miniscript/policy language** — heavy; multisig via PSBT covers near-term.
- **Mobile/desktop apps** — a product program, not a feature; after tester pilot.
- **Decentralized oracle for markets** — admin-attested first, honestly labeled.
- **Smart-contract VM** — explicitly out; the moat is Bitcoin-family simplicity.

## Suggested interleave

Tier A items are small and visible — fold them into the waves: Esplora layer
with Wave 7 (explorer), devnet+faucet-API+testkit with Wave 6 (SDK story),
webhooks with Wave 4 (they share the event plumbing), QR-PSBT with Wave 3.
Net add: ~4–5 sessions on top of the 22–27.
