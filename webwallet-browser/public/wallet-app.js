/* NetCoin wallet UI. Talks only to a same-origin relay (/api/*). The seed never
   leaves the browser; at rest it is AES-GCM encrypted with a password-derived key. */
"use strict";
(function () {
  const W = window.NCW;
  const API = (document.querySelector('meta[name="ncw-api"]')?.content || (location.origin + "/api")).replace(/\/$/, "");
  const STORE = "ncw.v1";
  const COIN = 100000000;

  let state = null; // { seed, privHex, address }
  let lastSpendableSats = 0;

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const screens = ["welcome", "create", "restore", "unlock", "walletView"];
  function show(id) { screens.forEach((s) => $(s).classList.toggle("hide", s !== id)); }
  const enc = new TextEncoder();
  const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

  function netToSats(str, { allowZero = false } = {}) {
    const m = String(str).trim().match(/^(\d+)(?:\.(\d{1,8}))?$/);
    if (!m) throw new Error("invalid amount");
    const whole = BigInt(m[1]); const frac = (m[2] || "").padEnd(8, "0");
    const sats = whole * 100000000n + BigInt(frac || "0");
    if (sats < 0n || (!allowZero && sats === 0n)) throw new Error("amount must be positive");
    if (sats > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("amount too large");
    return Number(sats);
  }
  const satsToNet = (s) => (s / COIN).toLocaleString(undefined, { maximumFractionDigits: 8 });
  function satsToInput(sats) {
    const n = BigInt(Math.max(0, Number(sats)));
    const whole = n / 100000000n;
    const frac = String(n % 100000000n).padStart(8, "0").replace(/0+$/, "");
    return frac ? `${whole}.${frac}` : String(whole);
  }
  function currentFeeSats() {
    return netToSats($("fee").value || "0", { allowZero: true });
  }
  function updateFeeHint() {
    try {
      const fee = currentFeeSats();
      const max = Math.max(0, lastSpendableSats - fee);
      $("feeHint").textContent = `Amount + fee must be less than your spendable balance. Max send now: ${satsToInput(max)} NET.`;
    } catch {
      $("feeHint").textContent = "Enter the network fee in NET, up to 8 decimal places.";
    }
  }

  // ---------- encryption at rest (WebCrypto) ----------
  async function deriveKey(password, salt) {
    const base = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: 200000, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
  }
  async function encryptSeed(seed, password) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(seed));
    return { salt: b64(salt), iv: b64(iv), ct: b64(ct) };
  }
  async function decryptSeed(blob, password) {
    const key = await deriveKey(password, unb64(blob.salt));
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct));
    return new TextDecoder().decode(pt);
  }

  function loadWallet(seed) {
    const privHex = W.privateKeyFromSeedPhrase(seed, 0);
    const w = W.walletFromPrivateKey(privHex);
    state = { seed, privHex, address: w.address };
    $("addr").textContent = w.address;
    show("walletView");
    refresh();
  }

  // ---------- node relay ----------
  async function api(path, opts) {
    const r = await fetch(API + path, opts);
    const text = await r.text();
    let data; try { data = JSON.parse(text); } catch { data = { error: text }; }
    if (!r.ok || data.error) throw new Error(data.error || ("HTTP " + r.status));
    return data;
  }

  async function refresh() {
    $("balNet").textContent = "…";
    try {
      const b = await api("/balance/" + encodeURIComponent(state.address));
      lastSpendableSats = b.spendable_sats ?? b.spendable ?? 0;
      $("balNet").textContent = satsToNet(lastSpendableSats);
      const imm = b.immature_sats ?? 0;
      $("balImmature").textContent = imm > 0 ? ("+" + satsToNet(imm) + " NET maturing") : "";
      updateFeeHint();
    } catch (e) { $("balNet").textContent = "—"; $("balImmature").textContent = "offline: " + e.message; }
  }

  async function send(toAddress, amountSats, feeSats) {
    const u = await api("/utxos?address=" + encodeURIComponent(state.address));
    const utxos = (u.utxos || []).map((x) => ({ txid: x.txid, vout: x.vout, amount: x.output.amount, address: x.output.address }));
    const signed = W.buildSignedPayment({
      privHex: state.privHex, utxos, toAddress, amount: amountSats, fee: feeSats, changeAddress: state.address,
    });
    const res = await api("/tx", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(signed) });
    return res.txid;
  }

  // ---------- wiring ----------
  $("btnCreate").onclick = () => {
    $("newPhrase").textContent = W.newSeedPhrase(16);
    $("createPw").value = ""; $("createErr").textContent = "";
    show("create");
  };
  $("btnCreateBack").onclick = () => show("welcome");
  $("btnCreateConfirm").onclick = async () => {
    const pw = $("createPw").value; const seed = $("newPhrase").textContent;
    if (pw.length < 8) { $("createErr").textContent = "Use a password of at least 8 characters."; return; }
    localStorage.setItem(STORE, JSON.stringify(await encryptSeed(seed, pw)));
    loadWallet(seed);
  };

  $("btnRestore").onclick = () => { $("restorePhrase").value = ""; $("restorePw").value = ""; $("restoreErr").textContent = ""; show("restore"); };
  $("btnRestoreBack").onclick = () => show("welcome");
  $("btnRestoreConfirm").onclick = async () => {
    const seed = $("restorePhrase").value.trim(); const pw = $("restorePw").value;
    if (!W.verifySeedPhrase(seed)) { $("restoreErr").textContent = "That recovery phrase is not valid."; return; }
    if (pw.length < 8) { $("restoreErr").textContent = "Use a password of at least 8 characters."; return; }
    localStorage.setItem(STORE, JSON.stringify(await encryptSeed(seed, pw)));
    loadWallet(seed);
  };

  $("btnUnlock").onclick = async () => {
    try {
      const blob = JSON.parse(localStorage.getItem(STORE));
      loadWallet(await decryptSeed(blob, $("unlockPw").value));
    } catch { $("unlockErr").textContent = "Wrong password."; }
  };
  $("btnForget").onclick = () => { if (confirm("Remove the encrypted wallet from this device? Make sure you have your recovery phrase.")) { localStorage.removeItem(STORE); show("welcome"); } };

  $("btnCopy").onclick = () => navigator.clipboard?.writeText(state.address);
  $("btnRefresh").onclick = refresh;
  $("btnLock").onclick = () => { state = null; show("unlock"); };
  $("fee").oninput = updateFeeHint;
  $("btnMax").onclick = () => {
    try {
      $("amount").value = satsToInput(Math.max(0, lastSpendableSats - currentFeeSats()));
      $("sendMsg").textContent = "";
    } catch (e) {
      $("sendMsg").className = "err";
      $("sendMsg").textContent = "Failed: " + e.message;
    }
  };
  $("btnSend").onclick = async () => {
    const msg = $("sendMsg"); msg.className = ""; msg.textContent = "Sending…";
    try {
      const to = $("toAddr").value.trim();
      W.addressToScriptPubkey(to); // validates it's a v0 net1 address
      const amt = netToSats($("amount").value);
      const fee = netToSats($("fee").value, { allowZero: true });
      if (lastSpendableSats && amt + fee > lastSpendableSats) {
        throw new Error(`amount + fee is too high. Max send is ${satsToInput(Math.max(0, lastSpendableSats - fee))} NET with this fee.`);
      }
      const txid = await send(to, amt, fee);
      msg.className = "ok"; msg.textContent = "Sent ✓ txid " + txid.slice(0, 16) + "…";
      $("toAddr").value = ""; $("amount").value = ""; setTimeout(refresh, 800);
    } catch (e) { msg.className = "err"; msg.textContent = "Failed: " + e.message; }
  };

  // ---------- boot ----------
  show(localStorage.getItem(STORE) ? "unlock" : "welcome");
})();
