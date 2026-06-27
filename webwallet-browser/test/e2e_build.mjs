import { readFileSync, writeFileSync } from "node:fs";
import { buildSignedPayment } from "../src/wallet.mjs";
const st = JSON.parse(readFileSync("/tmp/e2e_state.json", "utf8"));
const signed = buildSignedPayment({
  privHex: st.priv_hex,
  utxos: st.spendable_utxos,
  toAddress: st.recipient_address,
  amount: 3_000_000_000,   // 30 NET
  fee: 1000,
  changeAddress: st.change_address,
});
writeFileSync("/tmp/e2e_signed.json", JSON.stringify(signed));
console.log("JS built+signed tx: inputs=%d outputs=%d change=%d fee=%d",
  signed.inputs.length, signed.outputs.length, signed.change, signed.fee);
