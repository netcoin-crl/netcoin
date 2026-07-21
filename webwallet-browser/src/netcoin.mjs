// NetCoin non-custodial wallet crypto core.
//
// Pure functions only — no key ever leaves the caller. Mirrors the NetCoin
// Python protocol byte-for-byte (verified by test/crosscheck.mjs):
//   * compressed secp256k1 keys, P2WPKH (bech32, hrp "net", witver 0)
//   * sighash = double_sha256(canonical_json(payload))  (SIGHASH_ALL)
//   * ECDSA compact 64-byte r||s, low-s  (SIGHASH_ALL => no trailing flag byte)
import { secp256k1, schnorr } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { ripemd160 } from "@noble/hashes/ripemd160";
import { bytesToHex, hexToBytes, utf8ToBytes, concatBytes } from "@noble/hashes/utils";
import { bech32, bech32m, createBase58check } from "@scure/base";

export const HRP = "net";
export const P2PKH_VERSION = 0x35;
export const P2SH_VERSION = 0x75;
export const b58check = createBase58check(sha256);

export const doubleSha256 = (b) => sha256(sha256(b));
export const hash160 = (b) => ripemd160(sha256(b));

export function privToPub(privHex, compressed = true) {
  return bytesToHex(secp256k1.getPublicKey(hexToBytes(privHex), compressed));
}

// bech32 segwit v0 address (matches netcoin encode_witness_address(0, program)).
export function p2wpkhAddress(pubHex) {
  const program = hash160(hexToBytes(pubHex));
  const words = [0, ...bech32.toWords(program)];
  return bech32.encode(HRP, words);
}

// effective_script_pubkey for a P2WPKH output: "OP_0 <hash160hex>".
export function p2wpkhScriptPubkey(pubHex) {
  return "OP_0 " + bytesToHex(hash160(hexToBytes(pubHex)));
}

// ---- Legacy p2pkh + nested P2SH-SegWit (compatibility: existing coins) ----
export function legacyAddress(pubHex) {
  const payload = new Uint8Array(21);
  payload[0] = P2PKH_VERSION;
  payload.set(hash160(hexToBytes(pubHex)), 1);
  return b58check.encode(payload);
}

export function p2pkhScriptPubkey(pubHex) {
  return `OP_DUP OP_HASH160 ${bytesToHex(hash160(hexToBytes(pubHex)))} OP_EQUALVERIFY OP_CHECKSIG`;
}

// NetCoin scripts are text; the P2SH redeem script for nested segwit is the
// literal string "OP_0 <hash160hex>", hashed as UTF-8 bytes.
export function p2wpkhRedeemScript(pubHex) {
  return "OP_0 " + bytesToHex(hash160(hexToBytes(pubHex)));
}

export function p2shSegwitAddress(pubHex) {
  const redeemHash = hash160(new TextEncoder().encode(p2wpkhRedeemScript(pubHex)));
  const payload = new Uint8Array(21);
  payload[0] = P2SH_VERSION;
  payload.set(redeemHash, 1);
  return b58check.encode(payload);
}

export function p2shScriptPubkey(pubHex) {
  const redeemHash = hash160(new TextEncoder().encode(p2wpkhRedeemScript(pubHex)));
  return `OP_HASH160 ${bytesToHex(redeemHash)} OP_EQUAL`;
}

// ---- Taproot (key-path, BIP340) ----
// NetCoin key-path Taproot: witness v1 program = x-only pubkey (no tweak),
// bech32m address, schnorr signature over the same canonical-JSON sighash.
export function xonlyFromPriv(privHex) {
  return bytesToHex(schnorr.getPublicKey(hexToBytes(privHex)));
}

export function p2trAddress(xonlyHex) {
  const words = [1, ...bech32m.toWords(hexToBytes(xonlyHex))];
  return bech32m.encode(HRP, words);
}

// effective_script_pubkey for a P2TR output: "OP_1 <xonlyhex>".
export function p2trScriptPubkey(xonlyHex) {
  return "OP_1 " + xonlyHex;
}

// Canonical JSON identical to Python json.dumps(sort_keys=True,
// separators=(",",":")). Data is ASCII (hex / bech32 / integers), so
// JSON.stringify of leaf strings/ints matches Python exactly.
export function canonicalJson(v) {
  if (v === null) return "null";
  const t = typeof v;
  if (t === "boolean") return v ? "true" : "false";
  if (t === "number") {
    if (!Number.isInteger(v)) throw new Error("only integer numbers are supported");
    return String(v);
  }
  if (t === "bigint") return v.toString();
  if (t === "string") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(canonicalJson).join(",") + "]";
  if (t === "object") {
    const keys = Object.keys(v).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonicalJson(v[k])).join(",") + "}";
  }
  throw new Error("unsupported type in canonicalJson: " + t);
}

const SEQ_FINAL = 0xffffffff;

// SIGHASH_ALL preimage for one input. `tx` = {version, inputs:[{txid,vout,sequence?}],
// outputs:[{amount,address,script_pubkey?}], locktime}. `prevout` =
// {txid,vout,amount,address,script_pubkey}.
export function sighashAll(tx, inputIndex, prevout) {
  const inputs = tx.inputs.map((i) => {
    const o = { txid: i.txid, vout: i.vout };
    if (i.sequence !== undefined && i.sequence !== SEQ_FINAL) o.sequence = i.sequence;
    return o;
  });
  const outputs = tx.outputs.map((o) => {
    const out = { amount: o.amount, address: o.address };
    if (o.script_pubkey) out.script_pubkey = o.script_pubkey;
    return out;
  });
  const payload = {
    version: tx.version,
    inputs,
    outputs,
    locktime: tx.locktime,
    signing_input_index: inputIndex,
    prevout: {
      txid: prevout.txid,
      vout: prevout.vout,
      amount: prevout.amount,
      address: prevout.address,
      script_pubkey: prevout.script_pubkey,
    },
    sighash_type: "NETCOIN_ALL",
  };
  return doubleSha256(new TextEncoder().encode(canonicalJson(payload)));
}

// Sign a P2WPKH input. Returns the witness [sigHex, pubHex]; SIGHASH_ALL keeps
// the bare 64-byte signature (no trailing flag byte), matching the node.
export function signP2wpkhInput(tx, inputIndex, privHex, prevout) {
  const pubHex = privToPub(privHex, true);
  const digest = sighashAll(tx, inputIndex, prevout);
  const sig = secp256k1.sign(digest, hexToBytes(privHex)); // low-s + RFC6979 by default
  return [bytesToHex(sig.toCompactRawBytes()), pubHex];
}

// Sign a legacy p2pkh input: signature/public_key travel as fields (plus
// script_sig = "<sig> <pub>"), no witness.
export function signP2pkhInput(tx, inputIndex, privHex, prevout) {
  const pubHex = privToPub(privHex, true);
  const digest = sighashAll(tx, inputIndex, prevout);
  const sig = bytesToHex(secp256k1.sign(digest, hexToBytes(privHex)).toCompactRawBytes());
  return { signature: sig, public_key: pubHex, script_sig: `${sig} ${pubHex}` };
}

// Sign a nested P2SH-SegWit input: scriptSig reveals the redeem script,
// signature+pubkey go in the witness (same digest as everything else).
export function signP2shSegwitInput(tx, inputIndex, privHex, prevout) {
  const pubHex = privToPub(privHex, true);
  const digest = sighashAll(tx, inputIndex, prevout);
  const sig = bytesToHex(secp256k1.sign(digest, hexToBytes(privHex)).toCompactRawBytes());
  return { script_sig: p2wpkhRedeemScript(pubHex), witness: [sig, pubHex] };
}

// Sign a key-path P2TR input. Witness is [sigHex] only (BIP340 schnorr, 64
// bytes; SIGHASH_ALL adds no flag byte). Any valid BIP340 signature verifies —
// the node does not require a specific nonce derivation.
export function signP2trInput(tx, inputIndex, privHex, prevout) {
  const digest = sighashAll(tx, inputIndex, prevout);
  const sig = schnorr.sign(digest, hexToBytes(privHex), new Uint8Array(32));
  return [bytesToHex(sig)];
}

// ---- Signed messages (Bitcoin-style signmessage/verifymessage) ----
// Mirrors netcoin/crypto.py message_digest/sign_message byte-for-byte:
// double_sha256("\x18NetCoin Signed Message:\n" + varint(len(utf8)) + utf8),
// low-S ECDSA (RFC6979 k, noble's default), header byte = 27 + recovery + 4
// (always the "compressed" offset — this protocol never emits legacy 27-30).
const MESSAGE_MAGIC = utf8ToBytes("\x18NetCoin Signed Message:\n");

function messageVarint(n) {
  if (n < 0xfd) return Uint8Array.of(n);
  if (n <= 0xffff) return Uint8Array.of(0xfd, n & 0xff, (n >> 8) & 0xff);
  throw new Error("message too long");
}

export function messageDigest(message) {
  const body = utf8ToBytes(message);
  return doubleSha256(concatBytes(MESSAGE_MAGIC, messageVarint(body.length), body));
}

export function signMessage(privHex, message) {
  const digest = messageDigest(message);
  const sig = secp256k1.sign(digest, hexToBytes(privHex)); // low-S + RFC6979, like Python
  if (sig.recovery == null) throw new Error("signature missing recovery bit");
  const out = new Uint8Array(65);
  out[0] = 27 + sig.recovery + 4;
  out.set(sig.toCompactRawBytes(), 1);
  return btoa(String.fromCharCode(...out));
}
