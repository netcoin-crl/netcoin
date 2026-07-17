# NetCoin — Remaining Code Upgrades (handoff checklist)

This is a snapshot of what's genuinely **not done yet** in this codebase, for
handoff to another AI/developer. It reflects the real current state — several
items that older internal docs still list as "needed" are already built and
tested; those are called out explicitly below so you don't redo them.

## How to work in this repo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test,fast]"
python3 -m pytest -q          # full suite: ~900 tests, ~3.5 minutes, should be all green before you start
```

- Repo root: `netcoin/` (Python package), `sites/` (25 static subdomain
  sites — shared CSS/JS lives in `sites/shared/`, run
  `python3 tools/sync_site_shell_assets.py` after editing it), `tests/`
  (pytest, one file per feature area), `docs/` (reference docs — see
  `docs/NODES.md` for how the node/network works, `docs/REAL_VALUE_EXCHANGE_PLAN.md`
  for the long-range roadmap this checklist is drawn from).
- Every change should land with tests, and the full suite must stay green.
  This project has a strict "don't claim more than tests prove" culture —
  several tests literally assert phrases like `"does not claim mainnet readiness"`
  are present in tool output. Don't remove those assertions to make something
  pass.
- No code comments unless they explain a genuinely non-obvious *why* (a
  workaround, an invariant, a subtle bug history). Don't add speculative
  abstractions or config flags for hypothetical future needs.
- Before touching or deleting any file, grep for it across `tests/*.py` and
  `tools/*.py` first — this codebase has readiness-checker tools
  (`tools/check_m1_readiness.py`, `tools/check_m3_readiness.py`, etc.) that
  assert **exact strings** exist inside specific doc/site files. Removing or
  rewording those breaks real CI gates for no benefit.

## Already done — don't rebuild these

- **M-of-N P2SH multisig spending** (`netcoin/psbt.py`: `set_multisig_input`,
  `sign_multisig_input`, redeem-script-ordered scriptSig finalize; CLI:
  `psbt-sign --redeem-script`, `psbt-combine`). Tested end-to-end including
  out-of-order signing and tampered-signature rejection
  (`tests/test_multisig_spend_flow.py`, `tests/test_multisig_cli_flow.py`).
  What's still missing: a **wallet UI** for this (see item 3 below) — the
  backend and CLI are solid, nothing in the browser wallet exposes it yet.
- **Reorg-safe deposit crediting wired to the double-entry ledger**
  (`netcoin/exchange_deposit_watcher.py`) — detects a credited deposit's
  block falling off the main chain, reverses the ledger entry, flags the
  account if the customer already spent against it. Tested with real mined
  reorgs (`tests/test_exchange_deposit_reorg_drill.py`).
- **Ledger invariant enforcement** (`netcoin/exchange_accounting.py`:
  `invariant_check`, `reverse_reference`, `has_reference`,
  `customer_liability_sats`) — negative-liability detection, idempotent
  reversal. What's still missing: a standalone nightly-audit CLI tool and a
  kill-process chaos test (see item 6 below).
- **RBF/CPFP fee bumping** (`netcoin/fee_bump.py`) and **fee estimation**
  (`netcoin/node.py: fee_estimates_payload`, `/fee-estimates` endpoint) —
  fully implemented at the backend level. What's still missing: wallet UI
  wiring (a "Bump fee" button) — see item 3.
- **Hardware/offline signer interface** (`netcoin/signer.py`: `Signer`
  protocol, `HardwareSigner` with `CommandHardwareTransport`/
  `FileHardwareTransport`, `OfflineSigner`). What's still missing: a real
  vendor adapter tested against a physical device (see item 4) — the
  interface and file-drop/air-gapped flow are done and tested.
- **Proof of reserves** (`netcoin/exchange_reserves.py`) — full Merkle-sum
  liability tree, per-customer inclusion proofs, solvency attestation. Done.

## 1. Wallet UI for RBF and multisig (highest everyday-impact, no legal/hardware blocker)

The backend for both exists and is tested; nothing in `sites/wallet/` or the
local web wallet (`netcoin/webwallet.py`) surfaces them.

- [ ] Wallet UI: fee selector (fast/normal/economy) reading `/fee-estimates`;
      a "Bump fee" button on pending sends that calls `fee_bump.create_rbf_replacement`.
- [ ] Wallet UI: a "Create multisig wallet" flow — collect cosigner pubkeys,
      call `Wallet.create_multisig_address`, show the address + redeem
      script for backup.
- [ ] Wallet UI: a "Multisig spend" flow — build unsigned PSBT, export/import
      for each cosigner (reuse the existing PSBT export/import UI pattern
      already in the wallet), show signature-collection progress
      ("2 of 3 collected"), call `psbt.extract()` when ready.
- [ ] Tests: add browser/functional tests alongside the existing wallet UI
      test suite (`tests/test_webwallet.py`, `tests/test_m1_wallet_regressions.py`
      are the pattern to follow).

## 2. Hardware signer real-device adapter

- [ ] Implement one concrete `HardwareTransport` beyond the existing
      `FileHardwareTransport`/`CommandHardwareTransport`/
      `SimulatedHardwareTransport` — e.g. an HWI-style USB/HID bridge for a
      Trezor-class device, or a QR-based air-gapped signer profile.
- [ ] Fill the existing strict evidence gate (`hardware-wallet-device-testing`
      in `netcoin/mainnet_readiness.py`, schema in
      `tools/run_hardware_wallet_device_tests.py`) with a real device
      transcript once you have hardware to test against. This gate is
      already built and tested against evidence schema, just needs real
      device output.

## 3. Nightly ledger audit tool

- [ ] `tools/run_ledger_audit.py`: recompute all balances from
      `AccountingLedger`'s journal independently, compare to materialized
      balances, exit nonzero on drift. The `invariant_check()` method this
      would call already exists.
- [ ] `tests/test_ledger_chaos.py`: spawn a writer thread/process, `kill -9`
      it at random points across ~1000 iterations, assert `invariant_check()`
      stays green every time (sqlite3's `with conn:` context manager already
      makes each `post()` call atomic — this test proves it holds under real
      interruption, not just in theory).

## 4. Node decentralization footgun fixes

This directly caused a real incident this session (a local seed got banned
by the public seeds for advertising an unreachable address).

- [ ] `netcoin/node.py`: before `announce_self()` first fires, have the node
      dial its own advertised URL (`self_url`) from a fresh connection; if
      unreachable, skip announcing and surface a clear
      `advertise_unreachable` flag in `/info` and the webwallet Seed tab
      instead of silently getting banned later.
- [ ] `netcoin/cli.py`: reject obviously-wrong `--advertise` values at parse
      time — RFC1918 private ranges (`192.168.*`, `10.*`, `172.16-31.*`),
      loopback, and the RFC5737 documentation range (`203.0.113.*`, the
      literal example used in help text) — with an error explaining the
      public-IP + port-forward requirement.
- [ ] Add `GET /peers/echo-addr` (returns the caller's observed IP) so the
      webwallet Seed tab can show a "you entered X, your real IP looks like
      Y" mismatch warning without a third-party service.
- [ ] Tests: `tests/test_advertise_self_check.py` covering the reachability
      check and the rejected-address-format cases.

## 5. Nightly fuzz CI wiring

- [ ] `.github/workflows/nightly-fuzz.yml`: schedule
      `tools/run_nightly_fuzz_accumulator.py` (already exists and is tested —
      `tests/test_wave1_3_fuzz_accumulator.py`) to run nightly with corpus
      cached between runs via GitHub Actions cache; fail the job on any
      crash; upload the report as an artifact.
- [ ] Add two missing fuzz targets to the accumulator (current targets:
      tx-dict, rawtx, script): the P2P binary message decoder, and the PSBT
      parser (base64 + the new multisig `redeem_scripts`/`partial_sigs`
      fields).

## 6. Weak-rated items from the internal feature catalog

Run `python3 -c "from netcoin.feature_catalog import feature_catalog; import json; print(json.dumps(feature_catalog(), indent=2))"`
to see the full live catalog. As of this handoff, the lowest-rated items not
already covered above:

- [ ] **JSON-RPC compatibility test matrix** (`netcoin/rpc.py`) — add tests
      matching common JSON-RPC client expectations (Bitcoin-Core-style
      method names where applicable).
- [ ] **DNS seeder decentralization** (`netcoin/seeder.py`, tested in
      `tests/test_p6_dns_seeder.py`) — needs a second independently-operated
      DNS seed domain; this is more an operations task than a code task, but
      if you want to help the code side, make the seeder trivially
      deployable by a third party (a documented single-command bootstrap).
- [ ] **Migrations versioning** — every chain/app-store/index schema change
      should carry an explicit version number and a migration path (some of
      this exists in `netcoin/storage_migrations.py` — audit for gaps and
      extend the pattern to `netcoin/apps/__init__.py`'s AppStore schema and
      `netcoin/peerdb.py`).
- [ ] **Restore-drill automation** — `tools/run_recovery_drill.py`: fresh temp
      dir → install from a release artifact → recover a wallet from mnemonic
      → compare derived address/balance against a synced chain → emit an
      evidence JSON (there's an existing evidence-gate pattern in
      `netcoin/mainnet_readiness.py` to follow for the JSON shape).
- [ ] **Invalid block/tx fuzz corpus** — expand
      `tests/test_security_regressions.py`-style malformed-input cases into
      a larger corpus (hundreds of cases) checked into
      `tests/fuzz_regressions/` (ties into item 5).
- [ ] **Batch developer-rewards API load testing** — add a large-batch
      (1000+ recipients) performance test and a partial-failure test for
      `netcoin/apps/__init__.py`'s `create_batch_rewards`.
- [ ] **Publish the JS SDK to npm for real** — `sdk/netcoin-js` and
      `sdk/netcoin-developer` (both npm packages, currently install-from-git
      only) need an npm publish workflow. `sdk/netcoin-python` and
      `sdk/netcoin-rs` already exist as separate packages — check each one's
      README for current publish status before assuming any of them need
      building from scratch.

## Explicitly NOT code tasks — do not attempt these

These need a licensed audit firm, physical hardware, banking/legal
infrastructure, or real capital — no amount of code changes substitutes for
them. Full context in `docs/REAL_VALUE_EXCHANGE_PLAN.md` Phase 4.

- External security audit engagement
- FinCEN/state money-transmitter licensing, KYC/AML program, banking partner
- Real market-maker capital
- Physical hardware-wallet procurement (you can build the *adapter code* in
  item 2 above without a physical device by testing against
  `SimulatedHardwareTransport`, but don't claim the strict evidence gate is
  satisfied without a real device transcript — the gate is designed to
  refuse that)

## Verifying you're done with any item

Every item above should end with: `python3 -m pytest -q` fully green (no
regressions), a new test file or extended existing test file proving the
specific behavior, and no `!important`-style hacks or new abstractions beyond
what the task needs.
