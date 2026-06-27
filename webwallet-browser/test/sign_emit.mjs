import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url"; import { dirname, join } from "node:path";
import { signP2wpkhInput } from "../src/netcoin.mjs";
const here = dirname(fileURLToPath(import.meta.url));
const fx = JSON.parse(readFileSync(join(here, "fixtures.json"), "utf8"));
const tx = { version:1, locktime:0,
  inputs:[{ txid:"bb".repeat(32), vout:1 }],
  outputs:[{ amount:90000000, address:fx.p2wpkh_address }] };
const prevout = { txid:"bb".repeat(32), vout:1, amount:100000000,
  address:fx.p2wpkh_address, script_pubkey:fx.prevout_effective_script_pubkey };
const witness = signP2wpkhInput(tx, 0, fx.priv_hex, prevout);
const signedTx = { version:1, locktime:0,
  inputs:[{ txid:"bb".repeat(32), vout:1, signature:"", public_key:"", coinbase:"", witness }],
  outputs:[{ amount:90000000, address:fx.p2wpkh_address }] };
console.log(JSON.stringify({ signed_tx: signedTx, prevout }));
