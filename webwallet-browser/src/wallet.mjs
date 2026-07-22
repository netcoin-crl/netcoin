// NetCoin wallet logic: seed-phrase derivation (portable with the Python wallet)
// and transaction building. Pure functions; keys stay with the caller.
import { secp256k1 } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { hmac } from "@noble/hashes/hmac";
import { pbkdf2 } from "@noble/hashes/pbkdf2";
import { bytesToHex, hexToBytes, utf8ToBytes, randomBytes } from "@noble/hashes/utils";
import { bech32, bech32m } from "@scure/base";
import {
  privToPub, p2wpkhAddress, p2wpkhScriptPubkey, signP2wpkhInput,
  xonlyFromPriv, p2trAddress, p2trScriptPubkey, signP2trInput,
  legacyAddress, p2pkhScriptPubkey, p2shSegwitAddress, p2shScriptPubkey,
  signP2pkhInput, signP2shSegwitInput, b58check, P2PKH_VERSION, P2SH_VERSION, HRP,
} from "./netcoin.mjs";
import { bytesToHex as b2h } from "@noble/hashes/utils";
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
// addressType: "segwit" (default) or "taproot".
export function walletFromPrivateKey(privHex, addressType = "segwit") {
  const pubHex = privToPub(privHex, true);
  if (addressType === "taproot") {
    const xonly = xonlyFromPriv(privHex);
    return { privHex, pubHex, xonlyHex: xonly, addressType, address: p2trAddress(xonly), scriptPubkey: p2trScriptPubkey(xonly) };
  }
  if (addressType === "legacy") {
    return { privHex, pubHex, addressType, address: legacyAddress(pubHex), scriptPubkey: p2pkhScriptPubkey(pubHex) };
  }
  if (addressType === "p2sh-segwit") {
    return { privHex, pubHex, addressType, address: p2shSegwitAddress(pubHex), scriptPubkey: p2shScriptPubkey(pubHex) };
  }
  return { privHex, pubHex, addressType: "segwit", address: p2wpkhAddress(pubHex), scriptPubkey: p2wpkhScriptPubkey(pubHex) };
}

// Every address this key controls, one per type.
export function allWalletAddresses(privHex) {
  return {
    segwit: walletFromPrivateKey(privHex, "segwit").address,
    taproot: walletFromPrivateKey(privHex, "taproot").address,
    legacy: walletFromPrivateKey(privHex, "legacy").address,
    "p2sh-segwit": walletFromPrivateKey(privHex, "p2sh-segwit").address,
  };
}

// ---- transactions ----
// Derive the effective scriptPubkey for a NetCoin bech32/bech32m address:
// SegWit v0 -> "OP_0 <hash160>", Taproot v1 -> "OP_1 <xonly>".
export function addressToScriptPubkey(address) {
  const fail = () => { throw new Error("not a valid NetCoin address (SegWit net1q…, Taproot net1p…, Legacy, or P2SH)"); };
  try {
    const { prefix, words } = bech32.decode(address);
    if (prefix !== HRP || words[0] !== 0) fail();
    return "OP_0 " + bytesToHex(Uint8Array.from(bech32.fromWords(words.slice(1))));
  } catch { /* not bech32 v0: try bech32m v1 below */ }
  try {
    const { prefix, words } = bech32m.decode(address);
    if (prefix !== HRP || words[0] !== 1) fail();
    const program = Uint8Array.from(bech32m.fromWords(words.slice(1)));
    if (program.length !== 32) fail();
    return "OP_1 " + bytesToHex(program);
  } catch { /* not bech32m: try base58check below */ }
  try {
    const payload = b58check.decode(address);
    if (payload.length !== 21) fail();
    const h160 = b2h(payload.slice(1));
    if (payload[0] === P2PKH_VERSION) return `OP_DUP OP_HASH160 ${h160} OP_EQUALVERIFY OP_CHECKSIG`;
    if (payload[0] === P2SH_VERSION) return `OP_HASH160 ${h160} OP_EQUAL`;
    fail();
  } catch { fail(); }
}

// Consolidating coin selection: cover the target largest-first, then sweep in
// the smallest coins up to maxInputs so every send also shrinks the UTXO set.
// utxos: [{txid,vout,amount,(script_pubkey)}].
export function selectCoins(utxos, target, maxInputs = 500) {
  const desc = [...utxos].sort((a, b) => b.amount - a.amount);
  const core = [];
  let total = 0;
  for (const u of desc) {
    core.push(u);
    total += u.amount;
    if (total >= target) break;
  }
  if (total < target) throw new Error(`insufficient funds: have ${total}, need ${target}`);
  if (core.length > maxInputs) {
    const affordable = desc.slice(0, maxInputs).reduce((s, u) => s + u.amount, 0);
    throw new Error(`this send needs more than ${maxInputs} coins; you can send up to ${affordable} sats now — consolidate (send Max to yourself) to send more`);
  }
  const coreOps = new Set(core.map((u) => u.txid + ":" + u.vout));
  const chosen = [...core];
  for (const u of [...utxos].sort((a, b) => a.amount - b.amount)) {
    if (chosen.length >= maxInputs) break;
    if (coreOps.has(u.txid + ":" + u.vout)) continue;
    chosen.push(u); total += u.amount;
  }
  return { chosen, total };
}

const DUST = 546;

// Sign `chosen` UTXOs as inputs against a fixed `outputs` array. Shared by
// buildSignedPayment and buildUsernameClaim -- everything about a NetCoin
// spend is the same except what the outputs actually pay for.
function signInputsForOutputs(chosen, outputs, privHex, sequence, changeAddress) {
  const txCore = {
    version: 1,
    locktime: 0,
    inputs: chosen.map((u) => ({ txid: u.txid, vout: u.vout, sequence })),
    outputs,
  };
  const inputs = chosen.map((u, i) => {
    const prevout = {
      txid: u.txid, vout: u.vout, amount: u.amount,
      address: u.address || changeAddress,
      script_pubkey: u.script_pubkey || addressToScriptPubkey(u.address || changeAddress),
    };
    // Sign per prevout kind. All four address eras of this key are spendable.
    const spk = prevout.script_pubkey;
    if (spk.startsWith("OP_1 ")) {
      return { txid: u.txid, vout: u.vout, sequence, signature: "", public_key: "", coinbase: "", witness: signP2trInput(txCore, i, privHex, prevout) };
    }
    if (spk.startsWith("OP_DUP ")) {
      const f = signP2pkhInput(txCore, i, privHex, prevout);
      return { txid: u.txid, vout: u.vout, sequence, signature: f.signature, public_key: f.public_key, coinbase: "", script_sig: f.script_sig };
    }
    if (spk.startsWith("OP_HASH160 ")) {
      const f = signP2shSegwitInput(txCore, i, privHex, prevout);
      return { txid: u.txid, vout: u.vout, sequence, signature: "", public_key: "", coinbase: "", script_sig: f.script_sig, witness: f.witness };
    }
    return { txid: u.txid, vout: u.vout, sequence, signature: "", public_key: "", coinbase: "", witness: signP2wpkhInput(txCore, i, privHex, prevout) };
  });
  return { version: 1, locktime: 0, inputs, outputs };
}

// Build + sign a P2WPKH->P2WPKH payment. Returns the signed tx dict for POST /tx.
// All inputs must be P2WPKH controlled by `privHex` (single-key wallet).
export function buildSignedPayment({ privHex, utxos, toAddress, amount, fee, changeAddress, maxInputs = 500, rbf = false }) {
  amount = Number(amount); fee = Number(fee);
  if (!Number.isInteger(amount) || amount <= 0) throw new Error("amount must be a positive integer (sats)");
  if (!Number.isInteger(fee) || fee <= 0) throw new Error("fee must be a positive integer (sats)");
  const { chosen, total } = selectCoins(utxos, amount + fee, maxInputs);
  const change = total - amount - fee;
  // BIP125 opt-in RBF: any sequence below 0xfffffffe signals replaceability.
  const sequence = rbf ? 0xfffffffd : 0xffffffff;

  const outputs = [{ amount, address: toAddress }];
  if (change > DUST) outputs.push({ amount: change, address: changeAddress });

  const signed = signInputsForOutputs(chosen, outputs, privHex, sequence, changeAddress);
  return { ...signed, fee, change };
}

// Pay several recipients in a single transaction. One shared fee and one
// change output instead of a separate signed tx (and separate fee) per
// recipient -- same non-custodial build-and-sign path as a normal send.
export function buildBatchPayment({ privHex, utxos, recipients, fee, changeAddress, maxInputs = 500, rbf = false }) {
  fee = Number(fee);
  if (!Number.isInteger(fee) || fee <= 0) throw new Error("fee must be a positive integer (sats)");
  if (!Array.isArray(recipients) || recipients.length === 0) throw new Error("at least one recipient is required");
  if (recipients.length > 100) throw new Error("batch sends are limited to 100 recipients");
  let totalOut = 0;
  const outputs = recipients.map(({ address, amount }, i) => {
    amount = Number(amount);
    if (!address) throw new Error(`recipient ${i + 1} is missing an address`);
    if (!Number.isInteger(amount) || amount <= 0) throw new Error(`recipient ${i + 1} needs a positive integer amount (sats)`);
    totalOut += amount;
    return { amount, address };
  });
  const { chosen, total } = selectCoins(utxos, totalOut + fee, maxInputs);
  const change = total - totalOut - fee;
  const sequence = rbf ? 0xfffffffd : 0xffffffff;
  if (change > DUST) outputs.push({ amount: change, address: changeAddress });
  const signed = signInputsForOutputs(chosen, outputs, privHex, sequence, changeAddress);
  return { ...signed, fee, change, recipientCount: recipients.length, totalOut };
}

const USERNAME_PATTERN = /^[a-z0-9_-]{1,32}$/;

// Claim a username on-chain: a zero-value OP_RETURN output naming the
// username, alongside a real self-payment output in the same transaction.
// The chain indexer reads "whoever this tx also pays for real" as the
// claimant, so no separate proof-of-ownership step is needed -- owning the
// signing key that spent the inputs already proves it, the same way a normal
// send does.
export function buildUsernameClaim({ privHex, utxos, username, fee, changeAddress, maxInputs = 500 }) {
  fee = Number(fee);
  if (!Number.isInteger(fee) || fee <= 0) throw new Error("fee must be a positive integer (sats)");
  const name = String(username || "").trim().toLowerCase();
  if (!USERNAME_PATTERN.test(name)) throw new Error("username must be 1-32 characters: letters, numbers, dash, underscore");
  const { chosen, total } = selectCoins(utxos, fee + DUST, maxInputs);
  const change = total - fee;
  if (change < DUST) throw new Error("insufficient funds to cover the claim fee");
  const outputs = [
    { amount: change, address: changeAddress },
    { amount: 0, address: "", script_pubkey: `OP_RETURN NETCOIN_USERNAME ${name}` },
  ];
  const signed = signInputsForOutputs(chosen, outputs, privHex, 0xffffffff, changeAddress);
  return { ...signed, fee, change, username: name };
}

// Transfer an already-claimed username to a new owner. Only honored on-chain
// if this same transaction also spends a coin recorded as belonging to the
// CURRENT owner -- so `privHex` must control the current owner's address
// (one of `utxos` must actually belong to it), the same proof-of-control
// every other spend already requires.
export function buildUsernameTransfer({ privHex, utxos, username, toAddress, fee, changeAddress, maxInputs = 500 }) {
  fee = Number(fee);
  if (!Number.isInteger(fee) || fee <= 0) throw new Error("fee must be a positive integer (sats)");
  const name = String(username || "").trim().toLowerCase();
  if (!USERNAME_PATTERN.test(name)) throw new Error("username must be 1-32 characters: letters, numbers, dash, underscore");
  const { chosen, total } = selectCoins(utxos, fee + DUST * 2, maxInputs);
  const change = total - fee - DUST;
  if (change < 0) throw new Error("insufficient funds to cover the transfer fee");
  const outputs = [
    { amount: DUST, address: toAddress },
    { amount: 0, address: "", script_pubkey: `OP_RETURN NETCOIN_USERNAME_TRANSFER ${name}` },
  ];
  if (change > DUST) outputs.push({ amount: change, address: changeAddress });
  const signed = signInputsForOutputs(chosen, outputs, privHex, 0xffffffff, changeAddress);
  return { ...signed, fee, username: name, toAddress };
}
