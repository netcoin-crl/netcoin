# Consensus-Fidelity Plan (coordinated with Codex)

The remaining "match Bitcoin" features change the **signing / script-verification
consensus path** in `tx.py` and `script.py` — code that both agents (Claude and
Codex) touch. This document sequences that work and sets coordination rules so we
don't collide or introduce consensus bugs.

> Status as of v0.4.4: NetCoin already has P2SH/P2WPKH/P2WSH, Taproot **key-path**
> (Schnorr), a fuller-but-educational Script VM, full PSBT, descriptors, and HD
> wallets. What's missing vs Bitcoin is below, in priority order.

## Coordination rules (read first)

1. **Claim before you touch.** Before starting an item, record a claim in the
   `shared-memory` store (entity *NetCoin agent task coordination*) with
   `[author YYYY-MM-DD] CLAIMING <item> — files: tx.py/script.py`. One owner per
   item at a time.
2. **Lane split.** Claude owns consensus signing + Script; Codex owns P2P /
   networking / relay. Where they meet (tx serialization, witness layout),
   comment in the claim and ping the other.
3. **Small commits, push often.** Land each item in the smallest working unit.
   `git fetch` + check `HEAD..origin/main` before editing shared files.
4. **Green gate.** Full `pytest` must pass before every commit. New consensus
   behavior ships with tests, including negative/tamper cases.
5. **Backward compatibility.** Existing testnet data and signatures must stay
   valid. New behavior is opt-in via an explicit flag and defaults to today's
   semantics.

## Item 1 — Multiple SIGHASH types (do first; most bounded)  ✅ DONE (2026-06-22)

> Landed: `sighash_type` plumbed through `Transaction.sighash`/`sign_input`/
> `verify_input`; ALL/NONE/SINGLE + ANYONECANPAY; 1-byte flag on the signature;
> ALL kept byte-identical (full suite unchanged). Legacy P2PKH with a flag verifies
> directly in `tx.py` (the text Script VM can't recompute a per-flag digest); ALL
> still flows through `verify_script`. 9 tests in `tests/test_sighash.py`.


Today every input is signed with one implicit mode (`NETCOIN_ALL`). Add the
standard set so partial/flexible signing works:

- **ALL** (default, current behavior) — commit to all inputs + all outputs.
- **NONE** — commit to inputs, to no outputs.
- **SINGLE** — commit to inputs + only the output at the input's index.
- **ANYONECANPAY** (flag, combinable) — commit to only *this* input.

Design:
- Add `sighash_type` to `Transaction.sighash`, `sign_input`, `verify_input`.
- Build the digest by masking inputs/outputs per the mode (mirror BIP143 structure
  conceptually; exact byte layout stays NetCoin's JSON-canonical form).
- **Carry the type** with the signature: append a 1-byte sighash flag to the
  signature (legacy `script_sig` and witness item 0), so `verify_input` recomputes
  the right digest. Unknown/absent flag ⇒ ALL (back-compat).
- Mempool/policy: SINGLE with `index >= len(outputs)` is invalid; reject.

Tests: roundtrip per mode; SINGLE pins only its output (changing another output
stays valid, changing the paired output invalidates); ANYONECANPAY lets a second
input be added without breaking the first signature; tamper cases.

Risk: medium. Touches `tx.py` sign/verify only; no networking. **Claude leads.**

## Item 2 — Taproot script-path spends (BIP341/342)

Today Taproot is key-path only. Add script-path:

- **Tapscript leaf**: `(leaf_version=0xc0, script)`; leaf hash = tagged hash.
- **Merkle tree** of leaves; **tweak** the internal key by the tree's merkle root
  to get the output key (`Q = P + int(tweak)·G`).
- **Control block** in the witness: `[leaf_version|parity] || internal_key ||
  merkle_path`; verify it commits to the output key, then run the tapscript.
- Witness stack: `[...script inputs..., script, control_block]`.

Design touches `crypto.py` (taproot tweak + tagged hashes — partly present for
key-path), `script.py` (tapscript execution), `tx.py` (witness v1 script-path
branch in `verify_input`). Add address/descriptor support for `tr(internal,{tree})`.

Tests: build a 1-leaf and 2-leaf tree; spend via script-path; wrong control block
rejected; key-path still works; tweak vectors.

Risk: high (spans three modules). **Claude leads, after Item 1. Coordinate with
Codex on witness serialization.**

## Item 3 — Script-consensus polish (incremental, low risk each)

Pick off individually, each its own small PR:
- Strict DER + low-S signature encoding checks.
- `NULLDUMMY` (CHECKMULTISIG dummy must be empty) and `CLEANSTACK`.
- Sigop counting + per-block sigop limit.
- `OP_CHECKLOCKTIMEVERIFY` / `OP_CHECKSEQUENCEVERIFY` exact semantics with
  **median-time-past (BIP113)** for time-based locks.

Risk: low individually. Either agent; claim per item.

## Explicitly NOT doing (out of scope for an educational chain)

Exact byte-for-byte Bitcoin consensus, package relay / cluster mempool, and
mainnet anything. NetCoin stays *Bitcoin-like*, not Bitcoin Core.

## Suggested order

1. SIGHASH types (Item 1) — best value/effort, self-contained in `tx.py`.
2. Script-consensus polish (Item 3) — land a few quick wins.
3. Taproot script-path (Item 2) — the big one, last.
