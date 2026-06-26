// Verify the JS crypto core matches the NetCoin Python protocol byte-for-byte,
// using ground-truth fixtures emitted by tools/gen_fixtures.py.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { secp256k1 } from "@noble/curves/secp256k1";
import { hexToBytes } from "@noble/hashes/utils";
import {
  privToPub, p2wpkhAddress, p2wpkhScriptPubkey, sighashAll, signP2wpkhInput,
} from "../src/netcoin.mjs";

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

console.log(fails === 0 ? "\nALL CHECKS PASSED ✅" : `\n${fails} CHECK(S) FAILED ❌`);
process.exit(fails === 0 ? 0 : 1);
