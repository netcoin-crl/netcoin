// NetCoin wallet logic: seed-phrase derivation (portable with the Python wallet)
// and transaction building. Pure functions; keys stay with the caller.
import { secp256k1 } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { hmac } from "@noble/hashes/hmac";
import { pbkdf2 } from "@noble/hashes/pbkdf2";
import { bytesToHex, hexToBytes, utf8ToBytes, randomBytes } from "@noble/hashes/utils";
import { bech32 } from "@scure/base";
import {
  privToPub, p2wpkhAddress, p2wpkhScriptPubkey, signP2wpkhInput, HRP,
} from "./netcoin.mjs";
import WORD_LIST from "./wordlist.json" with { type: "json" };

const N = secp256k1.CURVE.n;
const WORD_INDEX = new Map(WORD_LIST.map((w, i) => [w, i]));

function bytesToBigInt(b) {
  let x = 0n;
  for (const byte of b) x = (x << 8n) | BigInt(byte);
  return x;
}
function bigIntTo32Hex(x) {
  return x.toString(16).padStart(64, "0");
}

// ---- seed phrase (matches netcoin.wallet) ----
export function newSeedPhrase(strengthBytes = 16) {
  if (![16, 24, 32].includes(strengthBytes)) throw new Error("strength must be 16/24/32");
  const entropy = randomBytes(strengthBytes);
  const checksum = sha256(entropy)[0];
  return [...entropy].map((b) => WORD_LIST[b]).concat(WORD_LIST[checksum]).join(" ");
}

export function seedPhraseToEntropy(phrase) {
  const words = phrase.trim().split(/\s+/);
  if (words.length < 2) throw new Error("seed phrase is too short");
  const values = new Uint8Array(words.length - 1);
  for (let i = 0; i < words.length - 1; i++) {
    if (!WORD_INDEX.has(words[i])) throw new Error("unknown word: " + words[i]);
    values[i] = WORD_INDEX.get(words[i]);
  }
  if (!WORD_INDEX.has(words[words.length - 1])) throw new Error("unknown checksum word");
  if (sha256(values)[0] !== WORD_INDEX.get(words[words.length - 1]))
    throw new Error("seed phrase checksum is invalid");
  return values;
}

export function verifySeedPhrase(phrase) {
  try { seedPhraseToEntropy(phrase); return true; } catch { return false; }
}

export function privateKeyFromSeedPhrase(phrase, index = 0) {
  const entropy = seedPhraseToEntropy(phrase);
  const seed = pbkdf2(sha256, entropy, utf8ToBytes("NetCoin seed phrase"), { c: 100000, dkLen: 32 });
  for (let counter = 0; ; counter++) {
    const digest = hmac(sha256, seed, utf8ToBytes(`netcoin-key/${index}/${counter}`));
    const key = bytesToBigInt(digest) % N;
    if (key >= 1n && key < N) return bigIntTo32Hex(key);
  }
}

export function newRandomPrivateKey() {
  for (;;) {
    const k = bytesToBigInt(randomBytes(32)) % N;
    if (k >= 1n) return bigIntTo32Hex(k);
  }
}

// A wallet view: address + scriptPubkey from a private key hex.
export function walletFromPrivateKey(privHex) {
  const pubHex = privToPub(privHex, true);
  return { privHex, pubHex, address: p2wpkhAddress(pubHex), scriptPubkey: p2wpkhScriptPubkey(pubHex) };
}

// ---- transactions ----
// Derive the effective scriptPubkey for a P2WPKH bech32 address: "OP_0 <hash160>".
export function addressToScriptPubkey(address) {
  const { prefix, words } = bech32.decode(address);
  if (prefix !== HRP) throw new Error("address has wrong network prefix");
  const witver = words[0];
  if (witver !== 0) throw new Error("only v0 (P2WPKH) addresses are supported here");
  const program = bech32.fromWords(words.slice(1));
  return "OP_0 " + bytesToHex(Uint8Array.from(program));
}

// Largest-first coin selection. utxos: [{txid,vout,amount,(script_pubkey)}].
export function selectCoins(utxos, target) {
  const sorted = [...utxos].sort((a, b) => b.amount - a.amount);
  const chosen = [];
  let total = 0;
  for (const u of sorted) {
    chosen.push(u);
    total += u.amount;
    if (total >= target) return { chosen, total };
  }
  throw new Error(`insufficient funds: have ${total}, need ${target}`);
}

const DUST = 546;

// Build + sign a P2WPKH->P2WPKH payment. Returns the signed tx dict for POST /tx.
// All inputs must be P2WPKH controlled by `privHex` (single-key wallet).
export function buildSignedPayment({ privHex, utxos, toAddress, amount, fee, changeAddress }) {
  amount = Number(amount); fee = Number(fee);
  if (!Number.isInteger(amount) || amount <= 0) throw new Error("amount must be a positive integer (sats)");
  if (!Number.isInteger(fee) || fee <= 0) throw new Error("fee must be a positive integer (sats)");
  const { chosen, total } = selectCoins(utxos, amount + fee);
  const change = total - amount - fee;

  const outputs = [{ amount, address: toAddress }];
  if (change > DUST) outputs.push({ amount: change, address: changeAddress });

  const txCore = {
    version: 1,
    locktime: 0,
    inputs: chosen.map((u) => ({ txid: u.txid, vout: u.vout })),
    outputs,
  };

  const inputs = chosen.map((u, i) => {
    const prevout = {
      txid: u.txid, vout: u.vout, amount: u.amount,
      address: u.address || changeAddress,
      script_pubkey: u.script_pubkey || addressToScriptPubkey(u.address || changeAddress),
    };
    const witness = signP2wpkhInput(txCore, i, privHex, prevout);
    return { txid: u.txid, vout: u.vout, signature: "", public_key: "", coinbase: "", witness };
  });

  return { version: 1, locktime: 0, inputs, outputs, fee, change };
}
