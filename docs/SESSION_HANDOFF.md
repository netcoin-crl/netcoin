# NetCoin — Full Session Handoff (for a fresh chat)

This document is written so a new assistant session can pick up NetCoin with
zero prior context. Read it fully before acting.

## 1. What NetCoin is
An educational, from-scratch, Bitcoin-like cryptocurrency in **pure Python**
(with an optional C accelerator). Public **testnet** — testnet NET has no
real-money value. UTXO + Proof-of-Work, Bitcoin-style concepts, different
network/address bytes, easy PoW so it mines on a laptop.

- **Current version: v0.12.0** (`pyproject.toml` + `netcoin/params.py:NODE_VERSION`).
- **Chain height: ~10,800+** and advancing (5-minute blocks live).
- Honest rating: **~8.5/10 as an educational chain, ~4/10 as production** (see §9).

## 2. Repositories & how to push
- **GitHub: `netcoin-crl/netcoin`** (private). Remote is
  `git@github-netcoin-crl:netcoin-crl/netcoin.git` (a host alias in `~/.ssh/config`).
- **Local working dir:** `/Users/adoniyasnegash/Documents/Playground/netcoin`.
  GitHub is the source of truth (the local dir vanished once historically).
- **Two gh accounts in the keyring:** `Adoniyas1` (read-only on the repo) and
  `netcoin-crl` (owner). **If `gh pr create` fails with "must be a collaborator",
  run `gh auth switch --user netcoin-crl` first.**
- **Pushing:** work has been committed **directly to `main`** and `git push origin main`
  in this project (the owner does this deliberately). PRs also work; CI must be green.
- **Release flow:** tag `vX.Y.Z` → `.github/workflows/release.yml` builds a
  checksummed zip and publishes a GitHub Release automatically (the workflow was
  fixed in v0.10.0 — do not put `secrets.*` in a step `if:`). Local release build:
  `bash tools/make_release.sh vX.Y.Z` → `dist/`.
- **Commit trailer used:** `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 3. AWS infrastructure (us-east-2)
Three public seeds, all one AWS account (this is the decentralization weakness):

| Seed | IP | Notes |
|---|---|---|
| seed1 | **18.220.89.128** | also runs the faucet, **all nginx sites**, and the user's separate "Final Trading Terminal" project on :3000/:8000/:8501 — **leave those alone** |
| seed2 | **18.220.197.20** | node only |
| seed3 | **18.226.74.252** | node only (usual canary for deploys) |

- **SSH:** `ssh ubuntu@<ip>`, key **`~/Downloads/final-aws-key.pem`**. Load once
  per session: `ssh-add ~/Downloads/final-aws-key.pem`. Passwordless sudo.
- **macOS gotcha:** the `timeout` command does NOT exist on macOS — do NOT wrap
  ssh in `timeout` (it silently fails and looks like "unreachable"). Use
  `ssh -o ConnectTimeout=N` instead.
- **ISP gotcha:** the user's home ISP (Charter/CUJO) blocks the `netcoin.online`
  DOMAIN (DNS + TLS SNI). Raw seed IPs work. Bash here runs on the user's Mac, so
  it's subject to the block — reach seeds via `ssh ubuntu@<ip> 'curl 127.0.0.1...'`
  (bypasses the block), not via the domain.
- **Node install:** `/opt/netcoin/netcoin-v2` (plain dir, NOT a git checkout),
  venv `.venv`, data `/opt/netcoin/.netcoin-testnet`, service `netcoin-node.service`
  on port **28444**. Faucet: `netcoin-faucet.service` (port 8081).
- **Node deploy:** `sudo bash /opt/netcoin/netcoin-v2/tools/deploy_seed.sh --zip /tmp/netcoin-X.Y.Z.zip`
  (backup → reinstall venv → test-gate → restart → 120s health check → auto-rollback).
  Canary seed3 first, then seed1/seed2.
- **Fast crypto is enabled on seeds:** systemd drop-in
  `/etc/systemd/system/netcoin-node.service.d/apikey.conf` sets
  `NETCOIN_APP_REQUIRE_API_KEY=1`; coincurve is installed so
  `NETCOIN_FAST_CRYPTO=1` is effective (`/info.node.crypto_backend` confirms).

## 4. Websites (18 live subdomains + shared shell)
- DNS at **IONOS** (not Route53). All subdomains → 18.220.89.128, one Let's
  Encrypt cert (18 SANs, auto-renew, LE email netcoin2006@gmail.com).
- Live sites in `/opt/netcoin/sites/<site>/`; nginx host-map in
  `/etc/nginx/sites-enabled/netcoin.conf`. Repo copies in `sites/<site>/`.
- **Static deploy:** `scp` the changed files to seed1 `/tmp`, back up the live
  copy, `sudo cp` into `/opt/netcoin/sites/<site>/`, `sudo chown root:root`.
- **Shared shell** (`sites/shared/site-shell.{js,css}`, copied into every site dir):
  Codex added **persona nav modes** (`nc.siteMode.v2`: Standard/Merchant/Developer/
  Operator/Governance/Labs) and **groups** (Basics/Commerce/Build/Operate/Trust/Labs).
  The shell also wraps `window.fetch` to **auto-register a free API key** so writes
  work under enforcement — do NOT remove that when editing the shell.
- Subdomains: wallet, explorer, pay, merchant, faucet, community, learn, download,
  nodes, network, status, security, governance, treasury, docs, api, markets, www(start).

## 5. Codebase map (`netcoin/`, ~12k lines)
- `chain.py` — consensus, validation, mining, mempool policy, persistence, **per-address
  UTXO index** (`_utxos_by_addr`, keeps balance/utxos O(coins-at-address)).
- `crypto.py` — self-rolled secp256k1/ECDSA/Bech32/Base58, BIP340 Schnorr. **ECDSA
  verify** has an optional **libsecp256k1/coincurve** fast path (`_fast_crypto_enabled`,
  `crypto_backend_status`), gated by `NETCOIN_FAST_CRYPTO`, **differentially tested**
  to accept the exact same sig set as pure Python (normalizes s to low-s). Signing +
  Schnorr are still pure Python (audit gap).
- `tx.py`, `script.py`, `block.py`, `serialization.py` — tx/script/block model.
- `node.py` — HTTP node (ThreadingHTTPServer), P2P gossip, peer reputation/ban-TTL,
  `/info` exposes `target_spacing_seconds`, `spacing_v2_activation_height`, `crypto_backend`.
- `apps/` — **package** (was apps.py): `routes.py`, `merchant.py`, `markets.py`,
  `polls.py`, `payouts.py`, `security.py`, `storage.py`. App-layer (invoices, tokens,
  usernames, escrow, webhooks, API keys). `route_app_get/route_app_post`.
- `wallet.py`, `webwallet.py` (local server wallet + `consolidate_coins`,
  `consolidation_status`), `hd.py`, `psbt.py`, `descriptors.py`, `taproot.py`.
- `emission.py`, `params.py`, `professional.py` (readiness checks), `storage.py`
  (SQLite backend, pruning, UTXO snapshots), `compact.py`, `blockfilter.py`,
  `channel.py`, `pool.py`, `miner.py`, `rpc.py`, `explorer*.py`.
- **Tests: 413** across `tests/*.py`. Run: `.venv/bin/python -m pytest tests/ -q`.
  Python venv: `python3.12 -m venv .venv && .venv/bin/pip install -e ".[test]"`.

## 6. Browser wallet (`webwallet-browser/` → deployed to `sites/wallet/`)
- Non-custodial, keys never leave the browser. Crypto core `src/netcoin.mjs`
  (secp256k1/schnorr via @noble, bech32/bech32m/base58check via @scure). Bundled
  by esbuild to `public/netcoin-wallet.js` (global `NCW`). Logic `src/wallet.mjs`.
  App/UI `public/wallet-app.js` (NOT bundled). Page `public/wallet.html` /
  `sites/wallet/index.html`.
- **All 4 address types** derive+spend (SegWit default `net1q`, Taproot `net1p`,
  Legacy, P2SH-SegWit) — address-type selector shows per-type balances.
- Reproducible signed build: `webwallet-browser/tools/build.sh` (npm ci + esbuild +
  SRI pin + GPG-sign MANIFEST). **GPG signing hangs non-interactively**; the key has
  no passphrase, so sign with:
  `gpg --batch --yes --pinentry-mode loopback --passphrase '' --armor --detach-sign --output MANIFEST.txt.asc MANIFEST.txt`.
- **CRITICAL SRI+cache gotcha (caused a lockout, fixed):** scripts are SRI-pinned.
  If you rebuild a script you MUST also change its `?v=` cache-buster in the HTML,
  or browsers serve a stale cached copy that fails the integrity hash → the browser
  **blocks the script** → `window.NCW` undefined → "Cannot read properties of
  undefined (reading 'walletFromPrivateKey')" and unlock fails as "wrong password".
  Always bump the `?v=` on EVERY changed script (netcoin-wallet.js AND wallet-app.js)
  when redeploying, and recompute SRI from the served file. **TODO: make build.sh
  auto-version every script so this can't recur.**
- **Send cap = 500 inputs** (`MAX_WALLET_SEND_INPUTS`, wallet.mjs `selectCoins` default 500;
  node accepts 1000). Coincurve makes big txs cheap to verify. Coin management:
  consolidating selection + `consolidate_coins` + `netcoin consolidate` CLI.
- **Fees are auto-calculated by transaction size** (v0.12 UI): Slow = network minimum
  for this tx's vsize (1 sat/vbyte, floor 500 sats), Normal = 10× Slow, Fast = 100× Slow;
  recomputed as the amount changes. `refreshAutoFees()` / `autoFeeTiers()` in wallet-app.js.

## 7. Economics & consensus params
- Subsidy: **50 NET × (9/10)^floor(height/265,000)** — 10% cut every 265,000 blocks,
  ~132.5M NET max. Activated at height 4,200 (legacy random window preserved 1,000–4,199).
- **Block time: 5 minutes from height 5,010** (spacing v2, NIP-0005, activation-gated,
  no chain reset). Below 5,010 it was 2-min. Retarget every 30 blocks; lone-miner
  floor rule prevents stalls. `params.target_spacing_at(h)`.
- Coinbase maturity 100 blocks. Relay caps: `MAX_STANDARD_TX_INPUTS=1000`,
  `MAX_MEMPOOL_ANCESTORS` raised, all env-overridable (`NETCOIN_MAX_*`).
- **Miners must run ≥ the version that has the next activation before that height,
  or they fork.** Payout address `net1qrre54elfs3dcglt8kwpxrnlqzk28n0wgvaupg4` (~6k NET).
- Mining one-off (no persistent daemon by default):
  `ssh ubuntu@18.226.74.252 'cd /opt/netcoin/netcoin-v2 && nohup .venv/bin/python -m netcoin miner --node http://127.0.0.1:28444 --address <addr> --address-type p2wpkh --blocks N --sync-after &'`

## 8. Auth (NIP-0004)
- `POST /api/keys/register` → free `nck_` developer key (hash stored, per-IP daily cap).
- `NETCOIN_APP_REQUIRE_API_KEY=1` gates all app-layer POSTs behind `X-Netcoin-Api-Key`;
  reads, `POST /tx`, and community posts/reports/votes stay open. **Enabled on seeds.**
- **Known gap:** keys identify an *app*, not a *coin owner* — token/username writes are
  forgeable. Signature-bound writes are the planned fix (see §9 #3).

## 9. The rating & the 10 biggest upgrades that raise it (production ~4/10)
Two ceilings can't be coded away: **(A) a paid third-party crypto audit** and
**(B) real independent node operators**. Nothing security-sensitive exceeds ~6 until (A).

**Top 10 features/changes that would upgrade the rating (do in this order):**
1. **Crypto audit** / move signing + Schnorr + address codec onto audited libs
   (verify already on libsecp256k1). *Needs funding for the audit.* — the ceiling.
2. **Real decentralization** — independent operators running seeds (one-command
   installer + node-diversity dashboard are the buildable enablers). *Needs people.*
3. **Signature-bound app-layer writes** (NIP-0008) — signed-message envelope proving
   control of the `from` address for token/username/escrow. **Pure code, highest value.**
4. **Wallet key hardening** — stop caching decrypted secret in sessionStorage;
   auto-lock; memory zeroing; hardware-wallet signing path.
5. **Second implementation / frozen consensus test vectors + independent verifier in CI.**
6. **Real persistence/scale** — SQLite backend default; covering indexes; verification
   off the request thread so big txs never stall reads.
7. **Hardened P2P** — addr-relay hardening, eclipse-attack resistance, per-peer DoS budgets,
   binary transport default.
8. **Monitoring/alerting/incident response** — Prometheus alerting, public status history,
   on-call runbook.
9. **Supply-chain/release hardening** — reproducible-build attestation, dep pinning/audit,
   CI-signed artifacts (+ auto-version wallet scripts to kill the SRI-cache class of bug).
10. **Economic-security honesty / mainnet plan** — document the lone-miner floor as
    permanent-testnet, or write a credible mainnet plan (checkpoints, sustained hashpower,
    fair launch). See `docs/UPGRADE_PLAN.md` for the full next-20 list & sequencing.

## 10. Gotchas checklist (bite people repeatedly)
- macOS has no `timeout` — use `ssh -o ConnectTimeout=`.
- ISP blocks the domain — use raw IPs / SSH-to-127.0.0.1.
- `gh auth switch --user netcoin-crl` before `gh pr create`.
- GPG signing: use `--pinentry-mode loopback --passphrase ''`.
- **Bump `?v=` on every changed SRI-pinned wallet script** or you lock users out.
- Don't touch seed1's Final Trading Terminal (:3000/:8000/:8501).
- `/opt/netcoin/netcoin-v2` and `/opt/netcoin/sites/` are NOT git checkouts.

## 11. Suggested next work
- **v0.13:** signature-bound app writes (#3) + NIP-0008. Highest-value code item.
- **v0.14:** Wallet/Pay visual remake (single-screen send, less scrolling) —
  auto-consolidate-then-send already partly there; cap is now 500 so the hard wall is gone.
- Then #6 (SQLite default + off-thread verify), #4 (key hardening), #8 (monitoring).
- Also fold auto-versioning of wallet scripts into `build.sh` (kills the SRI-cache bug class).

## 12. Shared memory
This project also uses a `shared-memory` MCP knowledge graph (shared with Codex).
Query it at task start (`read_graph` / `search_nodes`); record durable facts at the end.
Key entities: "NetCoin", "NetCoin Handoff 2026-07-02", and the per-release deployment
notes (v0.8–v0.12). Attribution rule: project facts anonymous; opinions/plans prefixed
`[author YYYY-MM-DD]`.
