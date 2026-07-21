// Verify the JS crypto core matches the NetCoin Python protocol byte-for-byte,
// using ground-truth fixtures emitted by tools/gen_fixtures.py.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { secp256k1 } from "@noble/curves/secp256k1";
import { hexToBytes } from "@noble/hashes/utils";
import { schnorr } from "@noble/curves/secp256k1";
import {
  privToPub, p2wpkhAddress, p2wpkhScriptPubkey, sighashAll, signP2wpkhInput,
  xonlyFromPriv, p2trAddress, p2trScriptPubkey, signP2trInput,
  legacyAddress, p2shSegwitAddress, signMessage,
} from "../src/netcoin.mjs";
import { privateKeyFromSeedPhrase, walletFromPrivateKey, verifySeedPhrase, addressToScriptPubkey, buildSignedPayment } from "../src/wallet.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const fx = JSON.parse(readFileSync(join(here, "fixtures.json"), "utf8"));

let fails = 0;
const check = (name, got, want) => {
  const ok = got === want;
  if (!ok) fails++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}`);
  if (!ok) console.log(`        got=${got}\n        want=${want}`);
};

// 1. key + address derivation
check("pubkey from priv", privToPub(fx.priv_hex), fx.pubkey_hex);
check("p2wpkh address", p2wpkhAddress(fx.pubkey_hex), fx.p2wpkh_address);
check("p2wpkh scriptPubkey", p2wpkhScriptPubkey(fx.pubkey_hex), fx.prevout_effective_script_pubkey);

// 2. THE gate: sighash digest must match Python exactly
const tx = {
  version: 1, locktime: 0,
  inputs: [{ txid: "aa".repeat(32), vout: 0 }],
  outputs: [
    { amount: 120000000, address: fx.p2wpkh_address },
    { amount: 379000000, address: fx.legacy_address },
  ],
};
const prevout = {
  txid: "aa".repeat(32), vout: 0, amount: 500000000,
  address: fx.p2wpkh_address, script_pubkey: fx.prevout_effective_script_pubkey,
};
const digestHex = Buffer.from(sighashAll(tx, 0, prevout)).toString("hex");
check("SIGHASH_ALL digest", digestHex, fx.sighash_all_digest_hex);

// 3. JS signature must be a valid secp256k1 sig over that digest for this pubkey
const [sigHex, pubHex] = signP2wpkhInput(tx, 0, fx.priv_hex, prevout);
const sigValid = secp256k1.verify(hexToBytes(sigHex), hexToBytes(fx.sighash_all_digest_hex), hexToBytes(pubHex));
check("JS signature verifies", sigValid, true);
check("witness pubkey matches", pubHex, fx.pubkey_hex);

// 4. cross-check: the Python-produced signature must also verify against our digest
const pySig = fx.signed_tx.inputs[0].witness[0];
const pyValid = secp256k1.verify(hexToBytes(pySig), hexToBytes(digestHex), hexToBytes(fx.pubkey_hex));
check("Python signature verifies against JS digest", pyValid, true);

// 5. seed-phrase derivation must match the Python wallet (mnemonic portability)
const seedPriv = privateKeyFromSeedPhrase(fx.seed.phrase, fx.seed.index);
check("seed phrase -> private key", seedPriv, fx.seed.priv_hex);
check("seed phrase -> p2wpkh address", walletFromPrivateKey(seedPriv).address, fx.seed.p2wpkh_address);
check("seed phrase validates", verifySeedPhrase(fx.seed.phrase), true);
check("addressToScriptPubkey round-trips", addressToScriptPubkey(fx.p2wpkh_address), fx.prevout_effective_script_pubkey);
// Legacy and P2SH base58 addresses are now first-class send targets.
check("legacy address resolves to p2pkh script", addressToScriptPubkey(fx.legacy_address).startsWith("OP_DUP OP_HASH160 "), true);
check("p2sh address resolves to p2sh script", addressToScriptPubkey(fx.p2sh_segwit_address).startsWith("OP_HASH160 "), true);

let zeroFeeRejected = false;
try {
  buildSignedPayment({
    privHex: fx.priv_hex,
    utxos: [{ txid: "aa".repeat(32), vout: 0, amount: 500000000, address: fx.p2wpkh_address }],
    toAddress: fx.p2wpkh_address,
    amount: 100000000,
    fee: 0,
    changeAddress: fx.p2wpkh_address,
  });
} catch {
  zeroFeeRejected = true;
}
check("zero-fee payment is rejected", zeroFeeRejected, true);

// 5b. signMessage must produce the exact Python signature (same digest, same
// low-S/RFC6979 signature, same recovery-bit header byte).
check("signMessage matches Python", signMessage(fx.priv_hex, fx.message.text), fx.message.signature_b64);

// 5. Taproot key-path: address, scriptPubkey, digest, and a verifying BIP340 sig
check("taproot xonly", xonlyFromPriv(fx.priv_hex), fx.taproot_xonly_hex);
check("taproot address", p2trAddress(fx.taproot_xonly_hex), fx.taproot_address);
check("taproot scriptPubkey", p2trScriptPubkey(fx.taproot_xonly_hex), fx.taproot_prevout_script_pubkey);
const trTx = { version: 1, locktime: 0, inputs: [{ txid: "bb".repeat(32), vout: 0 }], outputs: [{ amount: 399000000, address: fx.p2wpkh_address }] };
const trPrev = { txid: "bb".repeat(32), vout: 0, amount: 400000000, address: fx.taproot_address, script_pubkey: fx.taproot_prevout_script_pubkey };
check("taproot sighash digest", Buffer.from(sighashAll(trTx, 0, trPrev)).toString("hex"), fx.taproot_sighash_digest_hex);
const [trSigHex] = signP2trInput(trTx, 0, fx.priv_hex, trPrev);
check("taproot BIP340 sig verifies", String(schnorr.verify(hexToBytes(trSigHex), sighashAll(trTx, 0, trPrev), hexToBytes(fx.taproot_xonly_hex))), "true");

// 6. Legacy + nested-segwit address derivation matches Python base58check
check("legacy address", legacyAddress(fx.pubkey_hex), fx.legacy_address);
check("p2sh-segwit address", p2shSegwitAddress(fx.pubkey_hex), fx.p2sh_segwit_address);

console.log(fails === 0 ? "\nALL CHECKS PASSED ✅" : `\n${fails} CHECK(S) FAILED ❌`);
process.exit(fails === 0 ? 0 : 1);
