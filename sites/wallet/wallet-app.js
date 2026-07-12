/* NetCoin wallet UI. Talks only to a same-origin relay (/api/*). The seed never
   leaves the browser; at rest it is AES-GCM encrypted with a password-derived key. */
"use strict";
(function () {
  const W = window.NCW;
  const API = (document.querySelector('meta[name="ncw-api"]')?.content || (location.origin + "/api")).replace(/\/$/, "");
  const STORE = "ncw.v1"; // legacy single-wallet store
  const PROFILE_STORE = "ncw.profiles.v1";
  const CONTACTS_STORE = "ncw.contacts.v1";
  const LABELS_STORE = "ncw.txlabels.v1";
  const SEND_META_STORE = "ncw.sentMeta.v1";
  const WATCH_STORE = "ncw.watch.v1";
  const UI_MODE_STORE = "ncw.walletMode.v1";
  const ADDR_TYPE_STORE = "ncw.addrType.v1";
  const UI_TAB_STORE = "ncw.walletTab.v1";
  const SITE_MODE_STORE = "nc.siteMode.v1";
  const COIN = 100000000;
  const MAX_WALLET_SEND_INPUTS = 500;
  const SESSION_STORE = "ncw.unlockedSession.v2";
  const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
  const AUTO_LOCK_STORE = "ncw.autoLockMinutes.v1";
  const DEFAULT_AUTO_LOCK_MINUTES = 30;
  const AUTO_LOCK_OPTIONS = [0, 15, 30, 60, 120];
  const Vault = window.NCWVault || null;

  let state = null; // { secretType, seed?, privHex, address, profile }
  let lastSpendableSats = 0;
  let nodeSpacingSeconds = 120; // refreshed from /info; spacing v2 reports 300
  function walletAddressType() {
    const t = localStorage.getItem(ADDR_TYPE_STORE);
    return ["taproot", "legacy", "p2sh-segwit"].includes(t) ? t : "segwit";
  }
  async function annotateAddressTypeBalances() {
    // "All addresses are available if the wallet has them": show each type's
    // live balance in the selector so funds on any era of this key are visible.
    const sel = $("addrTypeSel");
    if (!sel || !state) return;
    const labels = { segwit: "SegWit — recommended default", taproot: "Taproot — modern, Schnorr-based", legacy: "Legacy — compatibility", "p2sh-segwit": "P2SH-SegWit — compatibility" };
    const addrs = W.allWalletAddresses(state.privHex);
    for (const opt of sel.options) {
      const type = opt.value;
      if (!addrs[type]) continue;
      try {
        const b = await api("/balance/" + encodeURIComponent(addrs[type]));
        const total = (b.total_sats ?? 0) / COIN;
        opt.textContent = labels[type] + (total > 0 ? " · has balance" : "");
      } catch { /* offline: keep plain labels */ }
    }
  }
  function setWalletAddressType(t) {
    localStorage.setItem(ADDR_TYPE_STORE, ["taproot", "legacy", "p2sh-segwit"].includes(t) ? t : "segwit");
    if (state) {
      const w = W.walletFromPrivateKey(state.privHex, walletAddressType());
      state.address = w.address;
      setAddressDisplay(w.address);
      if ($("addrTypeSel")) $("addrTypeSel").value = walletAddressType();
      makePaymentRequest();
      refresh();
      refreshMiningPanel();
    }
  }
  let pendingSend = null;
  let scanStream = null;
  let lastUtxos = [];
  let selectedOutpoints = new Set();

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const screens = ["welcome", "create", "restore", "privateKey", "unlock", "walletView"];
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
  const satsToNet = (s) => (s / COIN).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const satsToNetFull = (s) => (s / COIN).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 });
  const truncAddr = (a) => (a && a.length > 22) ? `${a.slice(0, 10)}…${a.slice(-6)}` : a;
  const setAddressDisplay = (a) => { const el = $("addr"); if (!el) return; el.textContent = truncAddr(a); el.title = a || ""; };
  const esc = (value) => String(value ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function satsToInput(sats) {
    const n = BigInt(Math.max(0, Number(sats)));
    const whole = n / 100000000n;
    const frac = String(n % 100000000n).padStart(8, "0").replace(/0+$/, "");
    return frac ? `${whole}.${frac}` : String(whole);
  }
  function currentFeeSats() {
    return netToSats($("fee").value || "0");
  }
  function updateFeeHint() {
    try {
      const fee = currentFeeSats();
      const max = Math.max(0, lastSpendableSats - fee);
      $("feeHint").textContent = `Amount + fee must be less than your spendable balance. Max send now: ${satsToInput(max)} NET.`;
    } catch {
      $("feeHint").textContent = "Enter a positive network fee in NET, up to 8 decimal places.";
    }
    updateCoinHealth();
  }

  function walletMaxSendableSats(feeSats = 0) {
    const top = [...lastUtxos].sort((a, b) => Number(b.amount || 0) - Number(a.amount || 0)).slice(0, MAX_WALLET_SEND_INPUTS);
    return Math.max(0, top.reduce((sum, u) => sum + Number(u.amount || 0), 0) - feeSats);
  }

  function updateCoinHealth() {
    const el = $("coinHealth");
    if (!el) return;
    if (!state) {
      el.className = "muted";
      el.textContent = "Coin status loads after unlock.";
      return;
    }
    if (!lastUtxos.length) {
      el.className = "muted";
      el.textContent = "Coin status loads after balance refresh.";
      return;
    }
    let fee = 0;
    try { fee = currentFeeSats(); } catch { /* fee field may be mid-edit */ }
    const maxOneSend = walletMaxSendableSats(fee);
    const stranded = Math.max(0, lastSpendableSats - fee - maxOneSend);
    const parts = [
      `${lastUtxos.length} spendable coin${lastUtxos.length === 1 ? "" : "s"}`,
      `max one-send ${satsToInput(maxOneSend)} NET`,
    ];
    if (lastUtxos.length > MAX_WALLET_SEND_INPUTS || stranded > 0) {
      el.className = "warn";
      parts.push(`consolidate to unlock ${satsToInput(stranded)} NET more in one payment`);
    } else if (lastUtxos.length > 120) {
      el.className = "warn";
      parts.push("consolidate soon to keep large sends smooth");
    } else {
      el.className = "muted";
      parts.push("coin set looks healthy");
    }
    el.textContent = parts.join(" · ");
  }

  function describeCoinSelectionProblem(amountSats, feeSats) {
    if (!lastUtxos.length) return "";
    try {
      W.selectCoins(lastUtxos, amountSats + feeSats, MAX_WALLET_SEND_INPUTS);
      return "";
    } catch (e) {
      const text = String(e?.message || e);
      if (!/more than|insufficient funds/i.test(text)) return text;
      const maxOneSend = walletMaxSendableSats(feeSats);
      if (amountSats + feeSats > lastSpendableSats) {
        return `Amount + fee is too high. Max spendable now is ${satsToInput(Math.max(0, lastSpendableSats - feeSats))} NET with this fee.`;
      }
      return `This payment needs too many small coins. Max one-send right now is ${satsToInput(maxOneSend)} NET. Use "Consolidate to self", confirm/mine that transaction, then send again.`;
    }
  }

  function setWalletStatus(text, ok = true) {
    const dot = $("statusDot");
    const status = $("walletStatus");
    if (!dot || !status) return;
    dot.className = ok ? "dot okdot" : "dot errdot";
    status.textContent = text;
  }

  function setBackupMsg(text, className = "muted") {
    const msg = $("backupMsg");
    if (!msg) return;
    msg.className = className;
    msg.textContent = text;
  }

  // ---------- wallet tab shell and modes ----------
  const WALLET_TABS = [
    { id: "wallet", label: "Wallet", modes: ["simple", "business", "advanced", "developer"] },
    { id: "mining", label: "Mining", modes: ["simple", "advanced", "developer"] },
    { id: "tokens", label: "Tokens", modes: ["business", "advanced", "developer"] },
    { id: "payments", label: "Payments", modes: ["business", "advanced", "developer"] },
    { id: "reports", label: "Reports", modes: ["business", "advanced", "developer"] },
    { id: "watch", label: "Watch-only", modes: ["advanced", "developer"] },
    { id: "escrow", label: "Escrow", modes: ["advanced", "developer"] },
    { id: "advanced", label: "Advanced", modes: ["advanced", "developer"] },
    { id: "contracts", label: "Contracts", modes: ["developer"] },
    { id: "developer", label: "Developer", modes: ["developer"] },
    { id: "settings", label: "Settings", modes: ["simple", "business", "advanced", "developer"] },
  ];
  const MODE_INFO = {
    simple: "Recommended for most users: send, receive, activity, contacts, and settings.",
    business: "Adds invoices, recurring payments, receipts, and reports.",
    advanced: "Adds watch-only wallets, escrow, coin control, PSBT, descriptors, and raw transaction tools.",
    developer: "Shows experimental app-layer contracts, polls, prediction-market demos, API/debug links, and raw tools. Use testnet/dev only.",
  };
  function walletUiMode() {
    const mode = localStorage.getItem(UI_MODE_STORE) || "simple";
    return MODE_INFO[mode] ? mode : "simple";
  }
  function siteModeToWalletMode(mode) {
    return { simple: "simple", merchant: "business", developer: "developer", node: "advanced", community: "simple", labs: "developer" }[mode] || "simple";
  }
  function walletModeToSiteMode(mode) {
    return { simple: "simple", business: "merchant", advanced: "node", developer: "developer" }[mode] || "simple";
  }
  function setWalletUiMode(mode, syncSite = true) {
    if (!MODE_INFO[mode]) mode = "simple";
    localStorage.setItem(UI_MODE_STORE, mode);
    if (syncSite) {
      const siteMode = walletModeToSiteMode(mode);
      if (window.NetCoinSiteMode?.setMode) window.NetCoinSiteMode.setMode(siteMode);
      else localStorage.setItem(SITE_MODE_STORE, siteMode);
    }
    applyWalletMode();
  }
  function syncWalletModeFromSite(siteMode) {
    const walletMode = siteModeToWalletMode(siteMode);
    if (walletMode && walletMode !== walletUiMode()) setWalletUiMode(walletMode, false);
    else applyWalletMode();
  }
  window.addEventListener("netcoin:siteModeChanged", (ev) => syncWalletModeFromSite(ev.detail?.mode));
  function activeWalletTab() {
    const tab = localStorage.getItem(UI_TAB_STORE) || "wallet";
    return ["overview", "send", "receive", "activity", "contacts"].includes(tab) ? "wallet" : tab;
  }
  function setActiveWalletTab(tab) {
    localStorage.setItem(UI_TAB_STORE, tab);
    applyWalletMode();
  }
  function tabAllowed(tabId, mode = walletUiMode()) {
    const tab = WALLET_TABS.find((t) => t.id === tabId);
    return !!tab && tab.modes.includes(mode);
  }
  function walletSection(title, bodyHtml, tab) {
    const card = document.createElement("div");
    card.className = "card wallet-section";
    card.dataset.walletTab = tab;
    card.innerHTML = `<h2>${title}</h2>${bodyHtml}`;
    return card;
  }
  function ensureWalletTabShell() {
    const wallet = $("walletView");
    if (!wallet || $("walletTabs")) return;

    function addWalletSection(section) { wallet.appendChild(section); }

    const tabs = document.createElement("div");
    tabs.id = "walletTabs";
    tabs.className = "wallet-tabs";
    tabs.setAttribute("role", "tablist");
    for (const tab of WALLET_TABS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.dataset.walletTabButton = tab.id;
      btn.textContent = tab.label;
      btn.onclick = () => setActiveWalletTab(tab.id);
      tabs.appendChild(btn);
    }
    wallet.prepend(tabs);
    const cards = Array.from(wallet.querySelectorAll(":scope > .card"));
    for (const card of cards) {
      let tab = "wallet";
      if (card.classList.contains("wallet-overview-card")) { tab = "wallet"; card.id = card.id || "wallet-home"; }
      else if (card.querySelector("#receiveOut")) { tab = "wallet"; card.id = card.id || "wallet-receive"; }
      else if (card.querySelector("#btnSend")) { tab = "wallet"; card.id = card.id || "wallet-send"; }
      else if (card.querySelector("#txHistory")) { tab = "wallet"; card.id = card.id || "wallet-activity"; }
      else if (card.querySelector("#contactsImportFile")) { tab = "settings"; card.id = card.id || "wallet-settings-backups"; }
      else if (card.querySelector("#statementOut")) tab = "reports";
      else if (card.querySelector("#walletDescriptor")) tab = "advanced";
      else if (card.querySelector("#watchList")) tab = "watch";
      card.classList.add("wallet-section");
      card.dataset.walletTab = tab;
    }

    addWalletSection(walletSection("Payments", `
      <p class="muted">Business payment tools live on the separated payment and merchant pages so the wallet stays clean.</p>
      <div class="section-links">
        <a href="https://pay.netcoin.online/"><b>Payment hub</b><br><span class="muted">Checkout, receipts, tips, donations, and profiles.</span></a>
        <a href="https://merchant.netcoin.online/"><b>Merchant dashboard</b><br><span class="muted">Invoices, POS, refunds, API keys, webhooks, and exports.</span></a>
      </div>`, "payments"));
    addWalletSection(walletSection("Mining", `
      <p class="muted">Mine NetCoin on your own computer and get the block reward paid to this wallet. No pools, no signup.</p>
      <p id="miningStats" class="muted">Checking chain status…</p>
      <p class="muted">1. Install NetCoin once (see the Learn site). 2. Activate your virtualenv. 3. Run the browser-address command below, or use the auto-harvest command if you mine with a local wallet file.</p>
      <pre id="mineCommand" class="mono">Unlock your wallet to see your personal mining command.</pre>
      <pre id="harvestMineCommand" class="mono">python -m netcoin miner --node http://18.220.89.128:28444 --wallet miner.json --blocks 0 --auto-harvest --harvest-every 25 --harvest-min-utxos 50</pre>
      <button id="btnCopyMineCommand" class="secondary" type="button">Copy mining command</button>
      <p class="muted">Mining rewards show under your balance as "maturing" and unlock after 100 blocks. If the netcoin.online domain is blocked on your network, the command above already uses the raw seed IP.</p>
      <div class="section-links"><a href="https://learn.netcoin.online/"><b>Full mining guide</b><br><span class="muted">Install steps, Windows/macOS/Linux notes, troubleshooting.</span></a></div>`, "mining"));
    addWalletSection(walletSection("Tokens", `
      <p class="muted">App-layer NET-20 tokens tracked by this node. Read-only here: token writes support wallet-signed app actions plus developer keys, but this browser wallet does not move app-layer tokens yet.</p>
      <button id="btnRefreshTokens" class="secondary" type="button">Refresh token balances</button>
      <div id="tokenList" class="watch-list"><span class="muted">Unlock the wallet, then refresh to load tokens.</span></div>
      <p class="muted">Create and manage tokens via the API — see <a href="https://api.netcoin.online/openapi.yaml" target="_blank" rel="noreferrer">the OpenAPI spec</a> or the SDKs.</p>`, "tokens"));
    addWalletSection(walletSection("Escrow", `
      <p class="muted">Escrow is an advanced app-layer workflow. Create and monitor 2-of-3 escrow deals from the separated markets/contract page.</p>
      <div class="section-links"><a href="https://markets.netcoin.online/"><b>Open escrow tools</b><br><span class="muted">Escrow, recurring agreements, polls, and contract templates.</span></a></div>`, "escrow"));
    addWalletSection(walletSection("Contracts", `
      <p class="muted">Developer-mode contract tools are intentionally separated from normal wallet use.</p>
      <div class="section-links"><a href="https://markets.netcoin.online/"><b>Open Phase 7 contracts</b><br><span class="muted">Timelock, vesting, multisig, recurring, polls, and prediction-market demos.</span></a></div>`, "contracts"));
    addWalletSection(walletSection("Developer", `
      <p class="muted">Developer tools expose raw/debug views and are intended for local/testnet use.</p>
      <div class="section-links">
        <a href="https://api.netcoin.online/"><b>API docs</b><br><span class="muted">Explorer/backend API reference and SDK links.</span></a>
      </div>`, "developer"));

    const settings = walletSection("Settings", `
      <p class="muted">Choose wallet mode and manage backups. Hidden tool groups are tucked away until you switch modes.</p>
      <label class="hide" for="walletUiMode">Wallet mode</label>
      <select id="walletUiMode" class="hide" aria-label="Wallet mode">
        <option value="simple">Simple — recommended</option>
        <option value="business">Business — invoices and reports</option>
        <option value="advanced">Advanced — coin control, escrow, PSBT</option>
        <option value="developer">Developer — raw/debug/testnet tools</option>
      </select>
      <div class="mode-grid" id="walletModeButtons"></div>
      <p id="walletModeHelp" class="muted compact-note"></p>
      <label for="sessionAutoLock">Session auto-lock</label>
      <select id="sessionAutoLock" aria-label="Session auto-lock timeout">
        <option value="15">15 minutes</option>
        <option value="30">30 minutes</option>
        <option value="60">1 hour</option>
        <option value="120">2 hours</option>
        <option value="0">Disabled for this tab</option>
      </select>
      <p id="sessionAutoLockStatus" class="muted auto-lock-status"></p>
      <details class="raw-details">
        <summary>What each mode shows</summary>
        <p class="muted">Simple: one compact wallet page with balance, send, receive, and activity. Merchant mode adds payments and reports. Advanced mode adds watch-only, escrow, coin control, PSBT, descriptors, and backups/settings tools. Developer mode adds contract/debug links.</p>
      </details>`, "settings");
    addWalletSection(settings);
    const modeButtons = $("walletModeButtons");
    if (modeButtons) {
      for (const [mode, text] of Object.entries(MODE_INFO)) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "secondary";
        btn.dataset.walletModeButton = mode;
        btn.textContent = mode[0].toUpperCase() + mode.slice(1);
        btn.title = text;
        btn.onclick = () => setWalletUiMode(mode);
        modeButtons.appendChild(btn);
      }
    }
    if ($("walletUiMode")) $("walletUiMode").onchange = () => setWalletUiMode($("walletUiMode").value);
  }
  function applyWalletMode() {
    const wallet = $("walletView");
    if (!wallet) return;
    ensureWalletTabShell();
    syncAutoLockControls();
    const mode = walletUiMode();
    let tab = activeWalletTab();
    if (!tabAllowed(tab, mode)) tab = "wallet";
    if ($("walletUiMode")) $("walletUiMode").value = mode;
    if ($("walletModeHelp")) $("walletModeHelp").textContent = MODE_INFO[mode];
    document.querySelectorAll("[data-wallet-mode-button]").forEach((btn) => btn.classList.toggle("active", btn.dataset.walletModeButton === mode));
    document.querySelectorAll("[data-wallet-tab-button]").forEach((btn) => {
      const allowed = tabAllowed(btn.dataset.walletTabButton, mode);
      btn.classList.toggle("hidden-tab", !allowed);
      btn.classList.toggle("active", allowed && btn.dataset.walletTabButton === tab);
      btn.setAttribute("aria-selected", allowed && btn.dataset.walletTabButton === tab ? "true" : "false");
    });
    document.querySelectorAll(".wallet-section").forEach((section) => {
      const visible = section.dataset.walletTab === tab && tabAllowed(section.dataset.walletTab, mode);
      section.classList.toggle("active-section", visible);
    });
  }

  function downloadText(filename, text, type = "application/json") {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function paymentUri(address, amount = "", label = "") {
    const qs = new URLSearchParams();
    if (String(amount || "").trim()) qs.set("amount", String(amount).trim());
    if (String(label || "").trim()) qs.set("label", String(label).trim());
    const query = qs.toString();
    return `netcoin:${address}${query ? "?" + query : ""}`;
  }

  function parsePaymentUri(value) {
    const raw = String(value || "").trim();
    if (!raw.toLowerCase().startsWith("netcoin:")) return null;
    const body = raw.slice(raw.indexOf(":") + 1);
    const [addressPart, queryPart = ""] = body.split("?");
    const params = new URLSearchParams(queryPart);
    return { address: decodeURIComponent(addressPart), amount: params.get("amount") || "", label: params.get("label") || "", message: params.get("message") || "" };
  }

  function normalizeRecipientField() {
    const parsed = parsePaymentUri($("toAddr").value);
    if (!parsed) return $("toAddr").value.trim();
    $("toAddr").value = parsed.address;
    if (parsed.amount) $("amount").value = parsed.amount;
    if (parsed.label && !$("contactName").value) $("contactName").value = parsed.label;
    return parsed.address;
  }

  function validateRecipientField() {
    const msg = $("addrValidation");
    try {
      const raw = $("toAddr").value.trim();
      if (!raw) {
        msg.className = "muted";
        msg.textContent = "Enter a NetCoin SegWit or Taproot address, or a payment link.";
        return false;
      }
      const parsed = parsePaymentUri(raw);
      const address = parsed ? parsed.address : raw;
      W.addressToScriptPubkey(address);
      msg.className = "ok";
      msg.textContent = parsed ? "Valid NetCoin payment link." : "Valid NetCoin address.";
      return true;
    } catch (e) {
      msg.className = "err";
      msg.textContent = "Address warning: " + e.message;
      return false;
    }
  }



  // ---------- offline QR renderer (byte-mode, ECC-L, versions 1-5) ----------
  const QR_L = {
    1: { data: 19, ecc: 7, align: [] },
    2: { data: 34, ecc: 10, align: [6, 18] },
    3: { data: 55, ecc: 15, align: [6, 22] },
    4: { data: 80, ecc: 20, align: [6, 26] },
    5: { data: 108, ecc: 26, align: [6, 30] },
  };

  function gfMul(x, y) {
    let z = 0;
    for (let i = 7; i >= 0; i--) {
      z = ((z << 1) ^ ((z & 0x80) ? 0x11d : 0)) & 0xff;
      if ((y >>> i) & 1) z ^= x;
    }
    return z;
  }

  function rsGenerator(degree) {
    let poly = [1];
    let root = 1;
    for (let i = 0; i < degree; i++) {
      const next = Array(poly.length + 1).fill(0);
      for (let j = 0; j < poly.length; j++) {
        next[j] ^= gfMul(poly[j], root);
        next[j + 1] ^= poly[j];
      }
      poly = next;
      root = gfMul(root, 2);
    }
    return poly.slice(0, degree);
  }

  function rsRemainder(data, degree) {
    const gen = rsGenerator(degree);
    const rem = Array(degree).fill(0);
    for (const b of data) {
      const factor = b ^ rem.shift();
      rem.push(0);
      for (let i = 0; i < degree; i++) rem[i] ^= gfMul(gen[i], factor);
    }
    return rem;
  }

  function pushBits(bits, value, length) {
    for (let i = length - 1; i >= 0; i--) bits.push((value >>> i) & 1);
  }

  function encodeQrCodewords(text) {
    const bytes = Array.from(new TextEncoder().encode(text));
    let version = 1;
    while (version <= 5 && 4 + 8 + bytes.length * 8 > QR_L[version].data * 8) version++;
    if (version > 5) throw new Error("payment link is too long for the bundled offline QR renderer");
    const spec = QR_L[version];
    const bits = [];
    pushBits(bits, 0b0100, 4); // byte mode
    pushBits(bits, bytes.length, 8);
    for (const b of bytes) pushBits(bits, b, 8);
    const cap = spec.data * 8;
    pushBits(bits, 0, Math.min(4, cap - bits.length));
    while (bits.length % 8) bits.push(0);
    const data = [];
    for (let i = 0; i < bits.length; i += 8) data.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));
    for (let pad = 0; data.length < spec.data; pad ^= 1) data.push(pad ? 0x11 : 0xec);
    return { version, codewords: data.concat(rsRemainder(data, spec.ecc)) };
  }

  function makeQrMatrix(text) {
    const { version, codewords } = encodeQrCodewords(text);
    const size = 17 + version * 4;
    const modules = Array.from({ length: size }, () => Array(size).fill(false));
    const reserved = Array.from({ length: size }, () => Array(size).fill(false));
    const set = (x, y, dark, res = true) => {
      if (x < 0 || y < 0 || x >= size || y >= size) return;
      modules[y][x] = !!dark;
      if (res) reserved[y][x] = true;
    };
    const finder = (x, y) => {
      for (let dy = -1; dy <= 7; dy++) for (let dx = -1; dx <= 7; dx++) {
        const xx = x + dx, yy = y + dy;
        const dark = dx >= 0 && dx <= 6 && dy >= 0 && dy <= 6 && (dx === 0 || dx === 6 || dy === 0 || dy === 6 || (dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4));
        set(xx, yy, dark);
      }
    };
    finder(0, 0); finder(size - 7, 0); finder(0, size - 7);
    for (let i = 8; i < size - 8; i++) {
      set(i, 6, i % 2 === 0);
      set(6, i, i % 2 === 0);
    }
    if (QR_L[version].align.length) {
      const pos = QR_L[version].align[1];
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
        const d = Math.max(Math.abs(dx), Math.abs(dy));
        set(pos + dx, pos + dy, d !== 1);
      }
    }
    for (let i = 0; i < 9; i++) { reserved[8][i] = true; reserved[i][8] = true; }
    for (let i = 0; i < 8; i++) { reserved[8][size - 1 - i] = true; reserved[size - 1 - i][8] = true; }
    set(8, size - 8, true);

    const bits = [];
    for (const cw of codewords) pushBits(bits, cw, 8);
    let bitIndex = 0;
    let upward = true;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right--;
      for (let vert = 0; vert < size; vert++) {
        const y = upward ? size - 1 - vert : vert;
        for (let j = 0; j < 2; j++) {
          const x = right - j;
          if (reserved[y][x]) continue;
          let dark = bitIndex < bits.length ? bits[bitIndex++] === 1 : false;
          if ((x + y) % 2 === 0) dark = !dark; // mask 0
          set(x, y, dark, false);
        }
      }
      upward = !upward;
    }

    // ECC level L (01) + mask 0, BCH protected and XOR masked.
    let format = 0b01000;
    let data = format << 10;
    for (let i = 14; i >= 10; i--) if ((data >>> i) & 1) data ^= 0x537 << (i - 10);
    const fmt = ((format << 10) | data) ^ 0x5412;
    const bit = (i) => ((fmt >>> i) & 1) === 1;
    for (let i = 0; i <= 5; i++) set(8, i, bit(i));
    set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
    for (let i = 0; i <= 5; i++) set(5 - i, 8, bit(9 + i));
    for (let i = 0; i <= 7; i++) set(size - 1 - i, 8, bit(i));
    for (let i = 8; i <= 14; i++) set(8, size - 15 + i, bit(i));
    return modules;
  }

  function renderPaymentQr(uri) {
    const canvas = $("qrCanvas");
    const msg = $("qrMsg");
    if (!canvas || !msg) return;
    const ctx = canvas.getContext("2d");
    try {
      const matrix = makeQrMatrix(uri);
      const quiet = 4;
      const scale = Math.floor(canvas.width / (matrix.length + quiet * 2));
      const used = (matrix.length + quiet * 2) * scale;
      const offset = Math.floor((canvas.width - used) / 2);
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#000";
      for (let y = 0; y < matrix.length; y++) for (let x = 0; x < matrix.length; x++) {
        if (matrix[y][x]) ctx.fillRect(offset + (x + quiet) * scale, offset + (y + quiet) * scale, scale, scale);
      }
      msg.className = "muted";
      msg.textContent = "Offline QR generated locally in this browser.";
    } catch (e) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      msg.className = "err";
      msg.textContent = "QR unavailable: " + e.message;
    }
  }

  function makePaymentRequest() {
    const out = $("receiveOut");
    try {
      const amount = $("requestAmount").value.trim();
      if (amount) netToSats(amount);
      const uri = paymentUri(state.address, amount, $("requestLabel").value);
      $("paymentUri").textContent = uri;
      renderPaymentQr(uri);
      out.classList.remove("hide");
    } catch (e) {
      out.classList.remove("hide");
      $("paymentUri").textContent = "Failed: " + e.message;
      renderPaymentQr("");
    }
  }

  async function copyPaymentLink() {
    const uri = $("paymentUri").textContent;
    if (uri) await navigator.clipboard?.writeText(uri);
  }

  async function sharePaymentLink() {
    const uri = $("paymentUri").textContent;
    if (!uri) return;
    if (navigator.share) await navigator.share({ title: "NetCoin payment request", text: uri });
    else await navigator.clipboard?.writeText(uri);
  }

  async function startQrScanner() {
    const box = $("scanBox");
    const video = $("scanVideo");
    const msg = $("scanMsg");
    if (!("BarcodeDetector" in window)) {
      msg.textContent = "This browser does not support built-in QR scanning. Paste the payment link instead.";
      box.classList.remove("hide");
      return;
    }
    if (scanStream) {
      scanStream.getTracks().forEach((t) => t.stop());
      scanStream = null;
      box.classList.add("hide");
      return;
    }
    try {
      box.classList.remove("hide");
      scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video.srcObject = scanStream;
      await video.play();
      const detector = new BarcodeDetector({ formats: ["qr_code"] });
      const tick = async () => {
        if (!scanStream) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) {
            const value = codes[0].rawValue || "";
            const parsed = parsePaymentUri(value);
            $("toAddr").value = parsed ? parsed.address : value;
            if (parsed?.amount) $("amount").value = parsed.amount;
            validateRecipientField();
            msg.textContent = "Scanned payment code.";
            scanStream.getTracks().forEach((t) => t.stop());
            scanStream = null;
            setTimeout(() => box.classList.add("hide"), 700);
            return;
          }
        } catch { /* keep scanning */ }
        requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      msg.textContent = "Camera unavailable: " + e.message;
    }
  }

  function loadLabels() {
    try { return JSON.parse(localStorage.getItem(LABELS_STORE) || "{}"); } catch { return {}; }
  }
  function saveLabels(labels) { localStorage.setItem(LABELS_STORE, JSON.stringify(labels || {})); }
  function txLabel(txid) { return String(loadLabels()[txid] || ""); }
  function setTxLabel(txid, label) { const labels = loadLabels(); if (label) labels[txid] = label; else delete labels[txid]; saveLabels(labels); }
  function loadSendMeta() {
    try { return JSON.parse(localStorage.getItem(SEND_META_STORE) || "{}"); } catch { return {}; }
  }
  function saveSendMeta(meta) { localStorage.setItem(SEND_META_STORE, JSON.stringify(meta || {})); }
  function contactForAddress(address) { return loadContacts().find((c) => sameAddress(c.address, address)); }
  function autoTxLabelForSend(toAddress) {
    const contact = contactForAddress(toAddress);
    return contact ? `Sent to ${contact.name}` : "";
  }
  function recordSentTxMeta(txid, toAddress, amountSats, feeSats) {
    if (!txid) return;
    const contact = contactForAddress(toAddress);
    const label = contact ? `Sent to ${contact.name}` : "";
    const meta = loadSendMeta();
    meta[txid] = { direction: "sent", to: toAddress, contactName: contact?.name || "", amountSats, feeSats, createdAt: Date.now() };
    saveSendMeta(meta);
    if (label && !txLabel(txid)) setTxLabel(txid, label);
  }

  // ---------- watch-only addresses ----------
  function loadWatchlist() {
    try {
      const raw = JSON.parse(localStorage.getItem(WATCH_STORE) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw
        .map((w) => ({ label: String(w.label || "").trim(), address: String(w.address || "").trim(), createdAt: Number(w.createdAt || 0) || Date.now() }))
        .filter((w) => w.address);
    } catch { return []; }
  }

  function saveWatchlist(list) {
    const clean = list
      .map((w) => ({ label: String(w.label || "").trim(), address: String(w.address || "").trim(), createdAt: Number(w.createdAt || 0) || Date.now() }))
      .filter((w) => w.address)
      .sort((a, b) => (a.label || a.address).localeCompare(b.label || b.address, undefined, { sensitivity: "base" }));
    localStorage.setItem(WATCH_STORE, JSON.stringify(clean));
  }

  function setWatchMsg(text, className = "muted") {
    const msg = $("watchMsg");
    if (!msg) return;
    msg.className = className;
    msg.textContent = text;
  }

  async function renderWatchlist() {
    const box = $("watchList");
    if (!box) return;
    const watches = loadWatchlist();
    if (!watches.length) {
      box.innerHTML = '<span class="muted">No watch-only addresses yet.</span>';
      return;
    }
    box.innerHTML = watches.map((w) => `<div class="watch-item" data-address="${esc(w.address)}"><div><strong>${esc(w.label || "Unlabeled")}</strong></div><div class="mono">${esc(w.address)}</div><div class="muted watchBal">Balance: checking…</div><button class="secondary smallbtn btnRemoveWatch" data-address="${esc(w.address)}" type="button">Remove</button></div>`).join("");
    document.querySelectorAll(".btnRemoveWatch").forEach((btn) => {
      btn.onclick = () => {
        saveWatchlist(loadWatchlist().filter((w) => !sameAddress(w.address, btn.dataset.address)));
        setWatchMsg("Watch-only address removed.", "ok");
        renderWatchlist();
      };
    });
    for (const item of box.querySelectorAll(".watch-item")) {
      const address = item.dataset.address;
      try {
        const b = await api("/balance/" + encodeURIComponent(address));
        const spendable = b.spendable_sats ?? b.spendable ?? 0;
        const total = b.total_sats ?? b.total ?? spendable;
        item.querySelector(".watchBal").textContent = `Balance: ${satsToNet(spendable)} NET spendable · ${satsToNet(total)} NET total`;
      } catch (e) {
        item.querySelector(".watchBal").textContent = "Balance unavailable: " + e.message;
      }
    }
  }

  function addWatchAddress() {
    try {
      const address = $("watchAddress").value.trim();
      if (!address) throw new Error("enter an address first");
      W.addressToScriptPubkey(address);
      const label = $("watchLabel").value.trim();
      const list = loadWatchlist();
      const idx = list.findIndex((w) => sameAddress(w.address, address));
      const row = { address, label, createdAt: idx >= 0 ? list[idx].createdAt : Date.now() };
      if (idx >= 0) list[idx] = row; else list.push(row);
      saveWatchlist(list);
      $("watchAddress").value = "";
      $("watchLabel").value = "";
      setWatchMsg(idx >= 0 ? "Updated watch-only address." : "Added watch-only address.", "ok");
      renderWatchlist();
    } catch (e) {
      setWatchMsg("Could not add watch-only address: " + e.message, "err");
    }
  }


  // ---------- saved contacts ----------
  function loadContacts() {
    try {
      const raw = JSON.parse(localStorage.getItem(CONTACTS_STORE) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw
        .map((c) => ({ name: String(c.name || "").trim(), address: String(c.address || "").trim(), group: String(c.group || "General").trim() || "General", createdAt: Number(c.createdAt || 0) || Date.now() }))
        .filter((c) => c.name && c.address);
    } catch {
      return [];
    }
  }

  function saveContacts(list) {
    const clean = list
      .map((c) => ({ name: String(c.name || "").trim(), address: String(c.address || "").trim(), group: String(c.group || "General").trim() || "General", createdAt: Number(c.createdAt || 0) || Date.now() }))
      .filter((c) => c.name && c.address)
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
    localStorage.setItem(CONTACTS_STORE, JSON.stringify(clean));
  }

  function shortAddress(address) {
    return address.length > 24 ? `${address.slice(0, 12)}…${address.slice(-8)}` : address;
  }

  function sameAddress(a, b) {
    return String(a || "").trim().toLowerCase() === String(b || "").trim().toLowerCase();
  }

  function outpointOf(utxo) {
    return `${utxo.txid}:${utxo.vout}`;
  }

  function setContactMsg(text, className = "muted") {
    const msg = $("contactMsg");
    msg.className = className;
    msg.textContent = text;
  }

  function renderContacts(selectedAddress = "") {
    const select = $("contactSelect");
    const contacts = loadContacts();
    const previous = selectedAddress || select.value;
    select.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = contacts.length ? "Select a saved contact…" : "No saved contacts yet";
    select.appendChild(placeholder);

    for (const contact of contacts) {
      const option = document.createElement("option");
      option.value = contact.address;
      option.textContent = `[${contact.group || "General"}] ${contact.name} — ${shortAddress(contact.address)}`;
      option.title = contact.address;
      if (sameAddress(contact.address, previous)) option.selected = true;
      select.appendChild(option);
    }
  }

  function useSelectedContact() {
    const address = $("contactSelect").value;
    if (!address) {
      setContactMsg("Choose a saved contact first.", "err");
      return;
    }
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    $("toAddr").value = address;
    if (contact) { $("contactName").value = contact.name; if ($("contactGroup")) $("contactGroup").value = contact.group || "General"; }
    setContactMsg(contact ? `Loaded ${contact.name}.` : "Loaded saved address.", "ok");
  }

  function saveCurrentRecipientAsContact() {
    try {
      const address = normalizeRecipientField();
      W.addressToScriptPubkey(address); // validates browser-supported net1 address
      const name = $("contactName").value.trim();
      if (!name) throw new Error("enter a contact name first");

      const contacts = loadContacts();
      const existingIndex = contacts.findIndex((c) => sameAddress(c.address, address));
      const group = ($("contactGroup")?.value || "General").trim() || "General";
      const contact = { name, address, group, createdAt: existingIndex >= 0 ? contacts[existingIndex].createdAt : Date.now() };
      if (existingIndex >= 0) contacts[existingIndex] = contact;
      else contacts.push(contact);

      saveContacts(contacts);
      renderContacts(address);
      setContactMsg(existingIndex >= 0 ? `Updated ${name}.` : `Saved ${name}.`, "ok");
    } catch (e) {
      setContactMsg("Could not save contact: " + e.message, "err");
    }
  }

  function deleteSelectedContact() {
    const address = $("contactSelect").value;
    if (!address) {
      setContactMsg("Choose a saved contact to delete.", "err");
      return;
    }
    const contacts = loadContacts();
    const contact = contacts.find((c) => sameAddress(c.address, address));
    const label = contact ? contact.name : shortAddress(address);
    if (!confirm(`Delete ${label} from saved contacts?`)) return;
    saveContacts(contacts.filter((c) => !sameAddress(c.address, address)));
    $("contactSelect").value = "";
    $("contactName").value = ""; if ($("contactGroup")) $("contactGroup").value = "General";
    renderContacts();
  renderWatchlist();
    setContactMsg(`Deleted ${label}.`, "ok");
  }

  function syncContactNameFromAddress() {
    const parsed = parsePaymentUri($("toAddr").value.trim());
    if (parsed) {
      $("amount").value = parsed.amount || $("amount").value;
      if (parsed.label && !$("contactName").value) $("contactName").value = parsed.label;
    }
    const address = parsed ? parsed.address : $("toAddr").value.trim();
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    if (contact) {
      $("contactName").value = contact.name;
      renderContacts(address);
    }
    validateRecipientField();
  }

  function exportContactsPlain() {
    const payload = { type: "netcoin-contacts", version: 1, exportedAt: new Date().toISOString(), contacts: loadContacts() };
    downloadText("netcoin-contacts.json", JSON.stringify(payload, null, 2));
    setBackupMsg("Contacts exported.", "ok");
  }

  async function exportContactsEncrypted() {
    const pw = $("contactsBackupPw").value;
    if (pw.length < 8) { setBackupMsg("Use a backup password of at least 8 characters.", "err"); return; }
    const payload = JSON.stringify({ type: "netcoin-contacts", version: 1, exportedAt: new Date().toISOString(), contacts: loadContacts() });
    downloadText("netcoin-contacts-encrypted.json", await encryptText(payload, pw));
    setBackupMsg("Encrypted contacts exported.", "ok");
  }

  async function importContactsFile(file) {
    if (!file) return;
    try {
      let text = await file.text();
      let data = JSON.parse(text);
      if (data.type === "netcoin-contacts-encrypted") {
        const pw = $("contactsBackupPw").value;
        if (pw.length < 8) throw new Error("enter the backup password first");
        data = JSON.parse(await decryptText(data, pw));
      }
      const incoming = Array.isArray(data) ? data : data.contacts;
      if (!Array.isArray(incoming)) throw new Error("file does not contain contacts");
      const merged = loadContacts();
      for (const contact of incoming) {
        const clean = { name: String(contact.name || "").trim(), address: String(contact.address || "").trim(), group: String(contact.group || "General").trim() || "General", createdAt: Number(contact.createdAt || 0) || Date.now() };
        if (!clean.name || !clean.address) continue;
        const idx = merged.findIndex((c) => sameAddress(c.address, clean.address));
        if (idx >= 0) merged[idx] = clean; else merged.push(clean);
      }
      saveContacts(merged);
      renderContacts();
  renderWatchlist();
      setBackupMsg("Contacts imported.", "ok");
    } catch (e) {
      setBackupMsg("Import failed: " + e.message, "err");
    }
  }

  // ---------- wallet profiles ----------
  function emptyProfiles() { return { active: "Default", profiles: {} }; }

  function loadProfiles() {
    if (Vault) return Vault.loadProfiles({ profileStore: PROFILE_STORE, legacyStore: STORE });
    let data;
    try { data = JSON.parse(localStorage.getItem(PROFILE_STORE) || "null"); } catch { data = null; }
    if (!data || typeof data !== "object" || !data.profiles || typeof data.profiles !== "object") data = emptyProfiles();
    const legacy = localStorage.getItem(STORE);
    if (legacy && !data.profiles.Default) {
      try { data.profiles.Default = JSON.parse(legacy); data.active = data.active || "Default"; saveProfiles(data); } catch { /* ignore invalid old store */ }
    }
    if (!data.active || !data.profiles[data.active]) data.active = Object.keys(data.profiles)[0] || "Default";
    return data;
  }

  function saveProfiles(data) {
    if (Vault) return Vault.saveProfiles(data, PROFILE_STORE);
    localStorage.setItem(PROFILE_STORE, JSON.stringify({ active: data.active || "Default", profiles: data.profiles || {} }));
  }

  function profileNames() { return Object.keys(loadProfiles().profiles).sort((a, b) => a.localeCompare(b)); }
  function hasProfiles() { return profileNames().length > 0; }

  function cleanProfileName(value, fallback = "Default") {
    const name = String(value || "").trim().replace(/[\n\r\t]/g, " ").slice(0, 40);
    return name || fallback;
  }

  function nextProfileName(prefix = "Wallet") {
    const names = new Set(profileNames());
    if (!names.has(prefix)) return prefix;
    let i = 2;
    while (names.has(`${prefix} ${i}`)) i += 1;
    return `${prefix} ${i}`;
  }

  function setActiveProfile(name) {
    const data = loadProfiles();
    if (data.profiles[name]) { data.active = name; saveProfiles(data); }
  }

  function saveEncryptedProfile(name, blob) {
    const clean = cleanProfileName(name, nextProfileName());
    const data = loadProfiles();
    data.profiles[clean] = blob;
    data.active = clean;
    saveProfiles(data);
    renderProfiles();
    return clean;
  }

  function encryptedProfile(name) {
    if (Vault) return Vault.encryptedProfile(name, { profileStore: PROFILE_STORE, legacyStore: STORE });
    const data = loadProfiles();
    return data.profiles[name || data.active];
  }

  function deleteProfile(name) {
    if (Vault) Vault.deleteProfile(name, { profileStore: PROFILE_STORE, legacyStore: STORE });
    else {
      const data = loadProfiles();
      delete data.profiles[name];
      data.active = Object.keys(data.profiles).sort()[0] || "Default";
      saveProfiles(data);
    }
    renderProfiles();
  }

  function renderProfiles() {
    const select = $("profileSelect");
    if (!select) return;
    const data = loadProfiles();
    const names = Object.keys(data.profiles).sort((a, b) => a.localeCompare(b));
    select.innerHTML = names.map((name) => `<option value="${esc(name)}"${name === data.active ? " selected" : ""}>${esc(name)}</option>`).join("");
    const msg = $("profileMsg");
    if (msg) msg.textContent = names.length ? `${names.length} encrypted wallet profile${names.length === 1 ? "" : "s"} saved in this browser.` : "No saved wallet profiles yet.";
  }

  function profileNameFromCreate() { return cleanProfileName($("createProfileName")?.value, nextProfileName()); }
  function profileNameFromRestore() { return cleanProfileName($("restoreProfileName")?.value, nextProfileName("Restored wallet")); }
  function profileNameFromPrivateKey() { return cleanProfileName($("privateKeyProfileName")?.value, nextProfileName("Private key wallet")); }

  function normalizePrivateKeyHex(value) {
    const clean = String(value || "").trim().replace(/^0x/i, "").replace(/\s+/g, "").toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(clean)) throw new Error("private key must be 64 hex characters");
    W.walletFromPrivateKey(clean);
    return clean;
  }

  function rememberUnlocked(secretType, secretValue, profile, force = false) {
    try {
      const keep = force || $("unlockRemember")?.checked || $("privateKeyRemember")?.checked;
      if (Vault) { Vault.rememberUnlocked(secretType, secretValue, profile, { store: SESSION_STORE, ttlMs: SESSION_TTL_MS, force, shouldRemember: keep }); return; }
      if (!keep) return;
      sessionStorage.setItem(SESSION_STORE, JSON.stringify({ type: secretType, value: secretValue, profile, expires: Date.now() + SESSION_TTL_MS }));
    } catch { /* ignore private browsing/session storage errors */ }
  }

  function clearUnlockedSession() {
    try { if (Vault) Vault.clearSession(SESSION_STORE); else sessionStorage.removeItem(SESSION_STORE); } catch { /* ignore */ }
  }

  function loadWalletFromPrivateKey(privHex, profile = loadProfiles().active, remember = true) {
    const clean = normalizePrivateKeyHex(privHex);
    const w = W.walletFromPrivateKey(clean, walletAddressType());
    state = { secretType: "privateKey", privHex: clean, address: w.address, profile };
    setAddressDisplay(w.address);
    if ($("activeProfilePill")) $("activeProfilePill").textContent = `Profile: ${profile} · private key · session unlocked`;
    if (remember) rememberUnlocked("privateKey", clean, profile, true);
    show("walletView");
    lastWalletActivityAt = Date.now();
    syncAutoLockControls();
    scheduleAutoLock();
    applyWalletMode();
    makePaymentRequest();
    refresh();
    loadHistory();
    loadUtxos();
    renderWatchlist();
    refreshDescriptorPanel();
    updateFeeEstimates();
    refreshMiningPanel();
    refreshTokenBalances();
  }

  function loadWalletSecret(secret, profile = loadProfiles().active, remember = true) {
    if (!secret || !secret.value) throw new Error("empty wallet secret");
    if (secret.type === "privateKey") return loadWalletFromPrivateKey(secret.value, profile, remember);
    return loadWallet(secret.value, profile, remember);
  }

  function resumeUnlockedSession() {
    try {
      const saved = Vault ? Vault.resumeSession(SESSION_STORE) : (() => {
        const raw = sessionStorage.getItem(SESSION_STORE);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || Number(parsed.expires || 0) < Date.now()) { clearUnlockedSession(); return null; }
        return parsed;
      })();
      if (!saved) return false;
      loadWalletSecret({ type: saved.type || "seed", value: saved.value }, cleanProfileName(saved.profile, loadProfiles().active), true);
      return true;
    } catch {
      clearUnlockedSession();
      return false;
    }
  }


  function autoLockMinutes() {
    const raw = Number(localStorage.getItem(AUTO_LOCK_STORE));
    return AUTO_LOCK_OPTIONS.includes(raw) ? raw : DEFAULT_AUTO_LOCK_MINUTES;
  }

  function autoLockLabel(minutes = autoLockMinutes()) {
    if (!minutes) return "Auto-lock disabled for this tab";
    return minutes >= 60 ? `Auto-lock after ${minutes / 60} hour${minutes === 60 ? "" : "s"} inactive` : `Auto-lock after ${minutes} minutes inactive`;
  }

  function syncAutoLockControls() {
    const minutes = autoLockMinutes();
    for (const id of ["unlockAutoLock", "privateKeyAutoLock", "sessionAutoLock"]) {
      const el = $(id);
      if (el) el.value = String(minutes);
    }
    const status = $("sessionAutoLockStatus");
    if (status) status.textContent = autoLockLabel(minutes);
  }

  function setAutoLockMinutes(value) {
    const minutes = AUTO_LOCK_OPTIONS.includes(Number(value)) ? Number(value) : DEFAULT_AUTO_LOCK_MINUTES;
    localStorage.setItem(AUTO_LOCK_STORE, String(minutes));
    syncAutoLockControls();
    scheduleAutoLock();
  }

  let autoLockTimer = null;
  let lastWalletActivityAt = Date.now();

  function clearAutoLockTimer() {
    if (autoLockTimer) window.clearTimeout(autoLockTimer);
    autoLockTimer = null;
  }

  function lockWallet(reason = "") {
    state = null;
    pendingSend = null;
    clearAutoLockTimer();
    clearUnlockedSession();
    renderProfiles();
    show(hasProfiles() ? "unlock" : "welcome");
    if (reason && $("profileMsg")) $("profileMsg").textContent = reason;
  }

  function scheduleAutoLock() {
    clearAutoLockTimer();
    if (!state) return;
    const minutes = autoLockMinutes();
    if (!minutes) return;
    const timeoutMs = minutes * 60 * 1000;
    const elapsed = Date.now() - lastWalletActivityAt;
    const remaining = Math.max(1000, timeoutMs - elapsed);
    autoLockTimer = window.setTimeout(() => {
      if (!state) return;
      if (Date.now() - lastWalletActivityAt >= timeoutMs) lockWallet(autoLockLabel(minutes) + ". Unlock again to continue.");
      else scheduleAutoLock();
    }, remaining);
  }

  function noteWalletActivity() {
    if (!state) return;
    lastWalletActivityAt = Date.now();
    scheduleAutoLock();
  }


  // ---------- encryption at rest (WebCrypto) ----------
  async function deriveKey(password, salt) {
    if (Vault) return Vault.deriveKey(password, salt);
    const base = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: 200000, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
  }
  async function encryptWalletSecret(secretType, secretValue, password) {
    if (Vault) return Vault.encryptWalletSecret(secretType, secretValue, password);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const plain = JSON.stringify({ type: secretType, value: secretValue });
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(plain));
    return { version: 2, type: secretType, salt: b64(salt), iv: b64(iv), ct: b64(ct) };
  }
  async function decryptWalletSecret(blob, password) {
    if (Vault) return Vault.decryptWalletSecret(blob, password);
    const key = await deriveKey(password, unb64(blob.salt));
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct));
    const text = new TextDecoder().decode(pt);
    if (blob && Number(blob.version || 1) >= 2) {
      const parsed = JSON.parse(text);
      return { type: parsed.type || "seed", value: parsed.value || "" };
    }
    return { type: "seed", value: text };
  }
  async function encryptSeed(seed, password) {
    return encryptWalletSecret("seed", seed, password);
  }
  async function decryptSeed(blob, password) {
    const secret = await decryptWalletSecret(blob, password);
    if (secret.type !== "seed") throw new Error("selected profile is not a recovery phrase profile");
    return secret.value;
  }

  async function encryptText(text, password) {
    if (Vault) return Vault.encryptText(text, password);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(text));
    return JSON.stringify({ type: "netcoin-contacts-encrypted", version: 1, salt: b64(salt), iv: b64(iv), ct: b64(ct) }, null, 2);
  }

  async function decryptText(blob, password) {
    if (Vault) return Vault.decryptText(blob, password);
    const key = await deriveKey(password, unb64(blob.salt));
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct));
    return new TextDecoder().decode(pt);
  }

  function loadWallet(seed, profile = loadProfiles().active, remember = true) {
    const privHex = W.privateKeyFromSeedPhrase(seed, 0);
    const w = W.walletFromPrivateKey(privHex, walletAddressType());
    state = { secretType: "seed", seed, privHex, address: w.address, profile };
    setAddressDisplay(w.address);
    if ($("activeProfilePill")) $("activeProfilePill").textContent = `Profile: ${profile} · seed phrase · session unlocked`;
    if (remember) rememberUnlocked("seed", seed, profile, true);
    show("walletView");
    lastWalletActivityAt = Date.now();
    syncAutoLockControls();
    scheduleAutoLock();
    applyWalletMode();
    makePaymentRequest();
    refresh();
    loadHistory();
    loadUtxos();
    renderWatchlist();
    refreshDescriptorPanel();
    updateFeeEstimates();
    refreshMiningPanel();
    refreshTokenBalances();
  }



  // ---------- descriptors and PSBT export ----------
  function setDescriptorMsg(text, className = "muted") {
    const msg = $("descriptorMsg");
    if (!msg) return;
    msg.className = className;
    msg.textContent = text;
  }

  function currentWalletDescriptor() {
    if (!state) return "";
    return `wpkh(${W.walletFromPrivateKey(state.privHex).pubHex})`;
  }

  function descriptorToWatchAddress(desc) {
    const text = String(desc || "").trim();
    const match = text.match(/^wpkh\(([0-9a-fA-F]{66}|[0-9a-fA-F]{130})\)$/);
    if (!match) throw new Error("browser import currently supports simple wpkh(<compressed-pubkey>) descriptors");
    return W.p2wpkhAddress(match[1]);
  }

  function refreshDescriptorPanel() {
    const box = $("walletDescriptor");
    if (box) box.value = currentWalletDescriptor();
  }

  function importDescriptorToWatchlist() {
    try {
      const desc = $("descriptorInput").value.trim();
      const address = descriptorToWatchAddress(desc);
      const list = loadWatchlist();
      const idx = list.findIndex((w) => sameAddress(w.address, address));
      const row = { address, label: "Descriptor watch", descriptor: desc, createdAt: idx >= 0 ? list[idx].createdAt : Date.now() };
      if (idx >= 0) list[idx] = row; else list.push(row);
      saveWatchlist(list);
      renderWatchlist();
      setDescriptorMsg(`Added descriptor watch address ${shortAddress(address)}.`, "ok");
    } catch (e) {
      setDescriptorMsg("Descriptor import failed: " + e.message, "err");
    }
  }

  function encodeNetPsbt(psbt) {
    return "netpsbt:" + btoa(JSON.stringify(psbt));
  }

  async function makeUnsignedPsbt() {
    try {
      const to = normalizeRecipientField();
      W.addressToScriptPubkey(to);
      const amount = netToSats($("amount").value);
      const fee = netToSats($("fee").value);
      if (!lastUtxos.length) await loadUtxos();
      const selected = selectedUtxos();
      const chosen = selected.length ? selected : W.selectCoins(lastUtxos, amount + fee).chosen;
      const total = chosen.reduce((sum, u) => sum + Number(u.amount || 0), 0);
      if (total < amount + fee) throw new Error("selected UTXOs do not cover amount + fee");
      const outputs = [{ amount, address: to }];
      const change = total - amount - fee;
      if (change > 546) outputs.push({ amount: change, address: state.address });
      const tx = {
        version: 1,
        locktime: 0,
        inputs: chosen.map((u) => ({ txid: u.txid, vout: u.vout })),
        outputs,
      };
      const prevouts = chosen.map((u) => ({ txid: u.txid, vout: u.vout, output: { amount: u.amount, address: u.address || state.address } }));
      const psbt = { magic: "netcoin-psbt-v1", tx, prevouts, created_at: new Date().toISOString(), note: "Unsigned browser wallet PSBT. Review offline before signing." };
      $("psbtOut").value = encodeNetPsbt(psbt);
      setDescriptorMsg("Unsigned PSBT created. Copy it for offline review/signing.", "ok");
    } catch (e) {
      setDescriptorMsg("PSBT creation failed: " + e.message, "err");
    }
  }

  // ---------- app-layer wallet reports / alerts / limits ----------
  function setWalletToolsMsg(text, className = "muted") {
    const msg = $("walletToolsMsg");
    if (!msg) return;
    msg.className = className;
    msg.textContent = text;
  }

  async function createWalletStatement() {
    if (!state) return;
    const out = $("statementOut");
    try {
      const month = encodeURIComponent($("statementMonth")?.value || "");
      const statement = await api(`/wallet/statement?address=${encodeURIComponent(state.address)}&month=${month}`);
      out.className = "mono";
      out.textContent = JSON.stringify(statement, null, 2);
      setWalletToolsMsg("Statement loaded from the app-layer API.", "ok");
    } catch (e) {
      out.className = "mono err";
      out.textContent = e.message;
      setWalletToolsMsg("Could not load statement: " + e.message, "err");
    }
  }

  async function downloadWalletStatementCsv() {
    if (!state) return;
    try {
      const month = encodeURIComponent($("statementMonth")?.value || "");
      const r = await fetch(`${API}/wallet/statement.csv?address=${encodeURIComponent(state.address)}&month=${month}`);
      const text = await r.text();
      if (!r.ok) throw new Error(text || "download failed");
      downloadText(`netcoin-statement-${state.address.slice(0, 8)}.csv`, text, "text/csv");
      setWalletToolsMsg("Statement CSV downloaded.", "ok");
    } catch (e) { setWalletToolsMsg("Could not download CSV: " + e.message, "err"); }
  }

  async function saveBalanceAlertRule() {
    if (!state) return;
    try {
      const threshold = $("alertThreshold").value || "0";
      const rule = await api("/wallet/alerts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address: state.address, threshold, kind: "balance_below", channel: "local" }) });
      setWalletToolsMsg("Saved alert rule " + rule.alert_id + ".", "ok");
    } catch (e) { setWalletToolsMsg("Could not save alert: " + e.message, "err"); }
  }

  async function saveSpendingLimits() {
    if (!state) return;
    try {
      const limits = await api("/wallet/limits", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ wallet_id: state.profile || state.address, address: state.address, single_tx_limit: $("singleTxLimit").value || "0", daily_limit: $("dailyLimit").value || "0", mode: $("walletSafetyMode").value || "daily", require_backup: $("requireBackupBeforeSpend")?.checked || false }) });
      setWalletToolsMsg("Saved spending limits for " + limits.wallet_id + ".", "ok");
    } catch (e) { setWalletToolsMsg("Could not save limits: " + e.message, "err"); }
  }

  async function checkSpendingLimits(amountSats, feeSats) {
    try {
      const check = await api("/wallet/limits/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ wallet_id: state.profile || state.address, address: state.address, amount_sats: amountSats, fee_sats: feeSats }) });
      if (!check.ok) throw new Error(check.reasons.join("; ") || "spending limit rejected this transaction");
      if (check.limits && check.limits.mode === "savings") {
        const phrase = prompt("Savings wallet mode is enabled. Type SEND to continue.");
        if (phrase !== "SEND") throw new Error("send cancelled by savings-mode confirmation");
      }
      return check;
    } catch (e) {
      if (/not an app-layer route|Failed to fetch/i.test(e.message)) return { ok: true, skipped: true };
      throw e;
    }
  }

  async function recordSpendForLimits(amountSats, feeSats) {
    try {
      await api("/wallet/spend-log", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ wallet_id: state.profile || state.address, address: state.address, amount_sats: amountSats, fee_sats: feeSats }) });
    } catch { /* old node or offline app-layer: ignore */ }
  }

  async function evaluateBalanceAlerts() {
    try {
      const r = await api("/wallet/alerts/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address: state?.address }) });
      if (r.triggered) setWalletToolsMsg(`${r.triggered} alert(s) triggered. Check wallet tools events.`, "warn");
      else setWalletToolsMsg("Alerts checked; none triggered.", "ok");
    } catch (e) { setWalletToolsMsg("Could not evaluate alerts: " + e.message, "err"); }
  }

  async function downloadWalletStatementPdf() {
    if (!state) return;
    try {
      const month = encodeURIComponent($("statementMonth")?.value || "");
      const r = await fetch(`${API}/wallet/statement.pdf?address=${encodeURIComponent(state.address)}&month=${month}`);
      const blob = await r.blob();
      if (!r.ok) throw new Error(await blob.text?.() || "download failed");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `netcoin-statement-${state.address.slice(0, 8)}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      setWalletToolsMsg("Statement PDF downloaded.", "ok");
    } catch (e) { setWalletToolsMsg("Could not download PDF: " + e.message, "err"); }
  }

  async function markBackupVerified() {
    if (!state) return;
    try {
      await api("/wallet/backup-health", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ wallet_id: state.profile || state.address, address: state.address, seed_verified: true, encrypted_export_saved: true }) });
      setWalletToolsMsg("Backup marked verified for this wallet profile.", "ok");
    } catch (e) { setWalletToolsMsg("Could not update backup health: " + e.message, "err"); }
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
      $("balNet").title = satsToNetFull(lastSpendableSats) + " NET";
      const imm = b.immature_sats ?? 0;
      let maturing = "";
      if (imm > 0) {
        maturing = "+" + satsToNet(imm) + " NET maturing";
        const blocks = Number(b.immature_all_mature_in_blocks || 0);
        if (blocks > 0) {
          const minutes = (blocks * nodeSpacingSeconds) / 60;
          const eta = minutes >= 90 ? `~${(minutes / 60).toFixed(1)} h` : `~${Math.ceil(minutes)} min`;
          maturing += ` · all spendable in ~${blocks} block${blocks === 1 ? "" : "s"} (${eta})`;
        }
      }
      $("balImmature").textContent = maturing;
      setWalletStatus("Online · balance refreshed " + new Date().toLocaleTimeString(), true);
      annotateAddressTypeBalances();
      updateFeeHint();
      loadHistory();
      loadUtxos();
      renderWatchlist();
    } catch (e) {
      $("balNet").textContent = "—";
      $("balImmature").textContent = "offline: " + e.message;
      setWalletStatus("Offline or stale data · " + e.message, false);
    }
  }

  async function refreshTokenBalances() {
    const box = $("tokenList");
    if (!box) return;
    box.innerHTML = '<span class="muted">Loading tokens…</span>';
    try {
      const d = await api("/tokens");
      const tokens = d.tokens || [];
      if (!tokens.length) {
        box.innerHTML = '<span class="muted">No app-layer tokens exist on this node yet.</span>';
        return;
      }
      const parts = [];
      for (const t of tokens.slice(0, 25)) {
        let mine = "—";
        if (state) {
          try {
            const b = await api(`/tokens/${encodeURIComponent(t.token_id)}/balance/${encodeURIComponent(state.address)}`);
            mine = `${b.amount} ${t.symbol}`;
          } catch { mine = "0"; }
        }
        parts.push(`<div class="watch-item"><div><strong>${esc(t.symbol)}</strong> — ${esc(t.name)}</div><div class="muted">Your balance: ${esc(mine)} · holders ${t.holder_count ?? 0} · ${t.mintable ? "mintable" : "fixed supply"}</div></div>`);
      }
      box.innerHTML = parts.join("");
    } catch (e) {
      box.innerHTML = `<span class="err">Tokens unavailable: ${esc(e.message)}</span>`;
    }
  }

  async function refreshMiningPanel() {
    try {
      const d = await api("/info");
      const n = d.node || d;
      nodeSpacingSeconds = Number(n.target_spacing_seconds || 0) || nodeSpacingSeconds;
      if ($("miningStats")) {
        const s = await api("/supply").catch(() => null);
        const reward = s ? `${s.next_subsidy} NET` : "—";
        const spacing = nodeSpacingSeconds % 60 === 0 ? `${nodeSpacingSeconds / 60} min` : `${nodeSpacingSeconds}s`;
        $("miningStats").innerHTML = `Chain height <strong>${esc(n.height)}</strong> · block reward <strong>${esc(reward)}</strong> · target block time <strong>${esc(spacing)}</strong>`;
      }
      if ($("mineCommand") && state) {
        $("mineCommand").textContent = `python -m netcoin miner --node http://18.220.89.128:28444 --address ${state.address} --address-type p2wpkh --blocks 0 --sync-after`;
      }
    } catch { /* offline: leave the static copy */ }
  }

  // ---- auto-calculated, size-based fees ----
  // The network min relay fee is 1 sat/vbyte. Slow = the real minimum for THIS
  // transaction's size; Normal = 10x that ("1000% more"); Fast = 10x Normal
  // ("another 1000%"). Fees therefore scale with how many coins a send spends,
  // so a big multi-input payment automatically pays enough to relay/confirm.
  const FEE_RATE_MIN_SATS_PER_VBYTE = 1; // matches node MIN_RELAY_FEE_PER_KB=1000
  const FEE_FLOOR_SATS = 500;            // keep tiny sends from looking like zero
  function estimateInputsForAmount(amountSats) {
    if (!lastUtxos.length) return 1;
    const desc = [...lastUtxos].sort((a, b) => Number(b.amount || 0) - Number(a.amount || 0));
    let total = 0, n = 0;
    for (const u of desc) { total += Number(u.amount || 0); n++; if (total >= amountSats) break; }
    return Math.max(1, Math.min(n, MAX_WALLET_SEND_INPUTS));
  }
  function estimateVsize(nInputs) {
    // segwit p2wpkh: ~68 vbytes/input, ~31/output (recipient + change), ~11 overhead.
    return 11 + nInputs * 68 + 2 * 31;
  }
  function autoFeeTiers(amountSats) {
    const nInputs = estimateInputsForAmount(amountSats);
    const slow = Math.max(FEE_FLOOR_SATS, Math.ceil(estimateVsize(nInputs) * FEE_RATE_MIN_SATS_PER_VBYTE));
    return { slow, normal: slow * 10, fast: slow * 100, inputs: nInputs };
  }
  function refreshAutoFees(keepCustom = true) {
    // Preserve a user's Custom fee; otherwise recompute from the current amount.
    const preset = $("feePreset");
    const wasCustom = keepCustom && preset && preset.value === "custom";
    let amountSats = 0;
    try { amountSats = netToSats($("amount").value, { allowZero: true }); } catch { amountSats = 0; }
    const t = autoFeeTiers(amountSats || lastSpendableSats || 0);
    if (preset) {
      const sel = wasCustom ? "custom" : (preset.value && preset.value !== "custom" ? preset.value : "normal");
      preset.innerHTML =
        `<option value="slow">Slow — ${satsToInput(t.slow)} NET (minimum)</option>` +
        `<option value="normal">Normal — ${satsToInput(t.normal)} NET (recommended)</option>` +
        `<option value="fast">Fast — ${satsToInput(t.fast)} NET</option>` +
        `<option value="custom">Custom</option>`;
      preset.value = sel === "slow" || sel === "fast" || sel === "custom" ? sel : "normal";
      preset._tiers = t;
      if (!wasCustom) $("fee").value = satsToInput(t[preset.value] ?? t.normal);
    }
    updateFeeHint();
  }
  async function updateFeeEstimates() { refreshAutoFees(false); }

  async function loadHistory() {
    if (!state || !$("txHistory")) return;
    try {
      const a = await api("/address/" + encodeURIComponent(state.address));
      const txids = (a.transaction_ids || []).slice(-10).reverse();
      if (!txids.length) {
        $("txHistory").innerHTML = '<span class="muted">No transactions yet.</span>';
        return;
      }
      const sentMeta = loadSendMeta();
      $("txHistory").innerHTML = txids.map((txid) => {
        const meta = sentMeta[txid] || {};
        const autoLabel = meta.contactName ? `Sent to ${meta.contactName}` : "";
        const label = txLabel(txid) || autoLabel;
        const subtitle = meta.to ? `To ${meta.contactName ? esc(meta.contactName) + " · " : ""}${esc(shortAddress(meta.to))}` : "Label saved only in this browser.";
        return `<div class="review tx-row"><div class="tx-row-head"><strong>${esc(label || "Transaction")}</strong><span class="muted">${subtitle}</span></div><div class="mono txid-line">${esc(txid)}</div><div class="row compact-row"><input data-txid="${esc(txid)}" class="txLabel" placeholder="Label this transaction" value="${esc(label)}" /><button class="secondary inline btnSaveTxLabel" data-txid="${esc(txid)}" type="button">Save</button></div></div>`;
      }).join("");
      document.querySelectorAll(".btnSaveTxLabel").forEach((btn) => {
        btn.onclick = () => {
          const txid = btn.dataset.txid;
          const input = document.querySelector(`.txLabel[data-txid="${txid}"]`);
          setTxLabel(txid, input.value.trim());
          btn.textContent = "Saved";
          setTimeout(() => { btn.textContent = "Save"; }, 900);
        };
      });
    } catch (e) {
      $("txHistory").innerHTML = `<span class="err">Could not load transaction history: ${e.message}</span>`;
    }
  }

  async function loadUtxos() {
    const summary = $("utxoSummary");
    const list = $("utxoList");
    if (!state || !summary || !list) return [];
    try {
      summary.textContent = "Loading spendable UTXOs…";
      const u = await api("/utxos?address=" + encodeURIComponent(state.address));
      lastUtxos = (u.utxos || []).map((x) => ({ txid: x.txid, vout: x.vout, amount: x.output.amount, address: x.output.address }));
      selectedOutpoints = new Set([...selectedOutpoints].filter((op) => lastUtxos.some((u) => outpointOf(u) === op)));
      renderUtxos();
      return lastUtxos;
    } catch (e) {
      list.innerHTML = "";
      summary.className = "err";
      summary.textContent = "Could not load UTXOs: " + e.message;
      return [];
    }
  }

  function selectedUtxos() {
    return lastUtxos.filter((u) => selectedOutpoints.has(outpointOf(u)));
  }

  function renderUtxos() {
    const summary = $("utxoSummary");
    const list = $("utxoList");
    if (!summary || !list) return;
    const selected = selectedUtxos();
    const selectedTotal = selected.reduce((sum, u) => sum + Number(u.amount || 0), 0);
    summary.className = "muted";
    summary.textContent = lastUtxos.length
      ? `${selected.length || "Auto"} selected · ${selected.length ? satsToInput(selectedTotal) + " NET" : "wallet will choose coins automatically"}`
      : "No spendable UTXOs returned by the node.";
    list.innerHTML = lastUtxos.map((u) => {
      const op = outpointOf(u);
      const checked = selectedOutpoints.has(op) ? " checked" : "";
      return `<div class="utxo-item"><label><input type="checkbox" class="utxoCheck" data-op="${esc(op)}"${checked} /><span><strong>${esc(satsToInput(u.amount))} NET</strong><br><span class="mono">${esc(op)}</span></span></label></div>`;
    }).join("");
    document.querySelectorAll(".utxoCheck").forEach((input) => {
      input.onchange = () => {
        if (input.checked) selectedOutpoints.add(input.dataset.op);
        else selectedOutpoints.delete(input.dataset.op);
        renderUtxos();
        updateFeeHint();
        updateCoinHealth();
      };
    });
    updateCoinHealth();
  }

  async function send(toAddress, amountSats, feeSats, forcedOutpoints = []) {
    if (!lastUtxos.length) await loadUtxos();
    const chosen = forcedOutpoints.length ? lastUtxos.filter((u) => forcedOutpoints.includes(outpointOf(u))) : lastUtxos;
    if (forcedOutpoints.length && chosen.length !== forcedOutpoints.length) throw new Error("one or more selected UTXOs are no longer spendable");
    const utxos = chosen.map((x) => ({ txid: x.txid, vout: x.vout, amount: x.amount, address: x.address }));
    const signed = W.buildSignedPayment({
      privHex: state.privHex, utxos, toAddress, amount: amountSats, fee: feeSats, changeAddress: state.address, maxInputs: MAX_WALLET_SEND_INPUTS,
    });
    const res = await api("/tx", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(signed) });
    return res.txid;
  }

  // ---------- wiring ----------
  let backupQuiz = null; // { indices: [i, j] } while the create-flow phrase check is active
  function resetBackupQuiz() {
    backupQuiz = null;
    $("backupQuiz")?.classList.add("hide");
    $("btnCreateConfirm")?.classList.remove("hide");
    if ($("quizWord1")) $("quizWord1").value = "";
    if ($("quizWord2")) $("quizWord2").value = "";
  }
  async function finishCreateWallet(verified) {
    const pw = $("createPw").value; const seed = $("newPhrase").textContent; const profile = profileNameFromCreate();
    saveEncryptedProfile(profile, await encryptSeed(seed, pw));
    resetBackupQuiz();
    loadWallet(seed, profile);
    if (verified) {
      // Best-effort: record verified backup in the optional app-layer backup-health tracker.
      api("/wallet/backup-health", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ wallet_id: profile, address: state.address, seed_verified: true }) }).catch(() => {});
    }
  }
  $("btnCreate").onclick = () => {
    $("newPhrase").textContent = W.newSeedPhrase(16);
    $("createProfileName").value = nextProfileName();
    $("createPw").value = ""; $("createErr").textContent = "";
    resetBackupQuiz();
    show("create");
  };
  $("btnCreateBack").onclick = () => { resetBackupQuiz(); show("welcome"); };
  $("btnCreateConfirm").onclick = () => {
    const pw = $("createPw").value;
    if (pw.length < 8) { $("createErr").textContent = "Use a password of at least 8 characters."; return; }
    const words = $("newPhrase").textContent.trim().split(/\s+/);
    const first = Math.floor(Math.random() * words.length);
    let second = Math.floor(Math.random() * (words.length - 1));
    if (second >= first) second += 1;
    backupQuiz = { indices: [first, second].sort((a, b) => a - b) };
    $("createErr").textContent = "";
    $("quizWordLabel1").textContent = `Word #${backupQuiz.indices[0] + 1} of your recovery phrase`;
    $("quizWordLabel2").textContent = `Word #${backupQuiz.indices[1] + 1} of your recovery phrase`;
    $("quizWord1").value = ""; $("quizWord2").value = "";
    $("btnCreateConfirm").classList.add("hide");
    $("backupQuiz").classList.remove("hide");
    $("quizWord1").focus();
  };
  $("btnQuizConfirm").onclick = async () => {
    if (!backupQuiz) { $("createErr").textContent = "Start over: generate a wallet first."; return; }
    const words = $("newPhrase").textContent.trim().split(/\s+/);
    const given = [$("quizWord1").value, $("quizWord2").value].map((w) => w.trim().toLowerCase());
    const expect = backupQuiz.indices.map((i) => words[i].toLowerCase());
    if (given[0] !== expect[0] || given[1] !== expect[1]) {
      $("createErr").textContent = "Those words do not match your recovery phrase. Check your written backup and try again.";
      return;
    }
    await finishCreateWallet(true);
  };
  $("btnQuizSkip").onclick = () => finishCreateWallet(false);

  $("btnPrivateKeyConfirm").onclick = async () => {
    try {
      const pw = $("privateKeyPw").value; const profile = profileNameFromPrivateKey();
      if (pw.length < 8) { $("privateKeyErr").textContent = "Use a password of at least 8 characters."; return; }
      const privHex = normalizePrivateKeyHex($("privateKeyInput").value);
      saveEncryptedProfile(profile, await encryptWalletSecret("privateKey", privHex, pw));
      loadWalletFromPrivateKey(privHex, profile);
    } catch (e) { $("privateKeyErr").textContent = "Import failed: " + e.message; }
  };
  $("btnPrivateKeySession").onclick = () => {
    try {
      const profile = profileNameFromPrivateKey();
      const privHex = normalizePrivateKeyHex($("privateKeyInput").value);
      loadWalletFromPrivateKey(privHex, profile);
    } catch (e) { $("privateKeyErr").textContent = "Unlock failed: " + e.message; }
  };

  $("btnRestore").onclick = () => { $("restorePhrase").value = ""; $("restoreProfileName").value = nextProfileName("Restored wallet"); $("restorePw").value = ""; $("restoreErr").textContent = ""; show("restore"); };
  $("btnPrivateKey").onclick = () => { $("privateKeyInput").value = ""; $("privateKeyProfileName").value = nextProfileName("Private key wallet"); $("privateKeyPw").value = ""; $("privateKeyErr").textContent = ""; show("privateKey"); };
  $("btnRestoreBack").onclick = () => show("welcome");
  $("btnPrivateKeyBack").onclick = () => show(hasProfiles() ? "unlock" : "welcome");
  $("btnRestoreConfirm").onclick = async () => {
    const seed = $("restorePhrase").value.trim(); const pw = $("restorePw").value; const profile = profileNameFromRestore();
    if (!W.verifySeedPhrase(seed)) { $("restoreErr").textContent = "That recovery phrase is not valid."; return; }
    if (pw.length < 8) { $("restoreErr").textContent = "Use a password of at least 8 characters."; return; }
    saveEncryptedProfile(profile, await encryptSeed(seed, pw));
    loadWallet(seed, profile);
  };

  $("btnUnlock").onclick = async () => {
    try {
      const profile = $("profileSelect").value || loadProfiles().active;
      setActiveProfile(profile);
      const blob = encryptedProfile(profile);
      if (!blob) throw new Error("profile not found");
      loadWalletSecret(await decryptWalletSecret(blob, $("unlockPw").value), profile);
    } catch { $("unlockErr").textContent = "Wrong password or missing profile."; }
  };
  $("profileSelect").onchange = () => setActiveProfile($("profileSelect").value);
  $("btnCreateAnother").onclick = () => $("btnCreate").onclick();
  $("btnRestoreAnother").onclick = () => $("btnRestore").onclick();
  $("btnPrivateKeyAnother").onclick = () => $("btnPrivateKey").onclick();
  $("btnForget").onclick = () => {
    const profile = $("profileSelect").value || loadProfiles().active;
    if (confirm(`Remove the encrypted wallet profile “${profile}” from this device? Make sure you have its recovery phrase.`)) {
      deleteProfile(profile);
      if (hasProfiles()) show("unlock"); else show("welcome");
    }
  };

  $("btnCopy").onclick = () => navigator.clipboard?.writeText(state.address);
  $("btnRefresh").onclick = refresh;
  if ($("addrTypeSel")) {
    $("addrTypeSel").value = walletAddressType();
    $("addrTypeSel").onchange = () => setWalletAddressType($("addrTypeSel").value);
  }
  document.addEventListener("click", (ev) => {
    if (ev.target && ev.target.id === "btnRefreshTokens") refreshTokenBalances();
  });
  document.addEventListener("click", (ev) => {
    if (ev.target && ev.target.id === "btnCopyMineCommand") navigator.clipboard?.writeText($("mineCommand")?.textContent || "");
  });
  for (const eventName of ["pointerdown", "keydown", "input", "change"]) {
    document.addEventListener(eventName, noteWalletActivity, { capture: true, passive: true });
  }
  document.addEventListener("change", (ev) => {
    if (["unlockAutoLock", "privateKeyAutoLock", "sessionAutoLock"].includes(ev.target?.id)) setAutoLockMinutes(ev.target.value);
  });
  syncAutoLockControls();
  $("btnLock").onclick = () => lockWallet();
  $("fee").oninput = () => { $("feePreset").value = "custom"; updateFeeHint(); };
  $("feePreset").onchange = () => {
    const p = $("feePreset");
    if (p.value !== "custom") {
      const tiers = p._tiers || autoFeeTiers(0);
      $("fee").value = satsToInput(tiers[p.value] ?? tiers.normal);
      updateFeeHint();
    }
  };
  // Recompute size-based fees whenever the amount changes (more coins => higher min).
  $("amount").addEventListener("input", () => refreshAutoFees(true));
  $("btnMakePaymentLink").onclick = makePaymentRequest;
  $("btnCopyPaymentLink").onclick = copyPaymentLink;
  $("btnSharePaymentLink").onclick = sharePaymentLink;
  $("btnScanQr").onclick = startQrScanner;
  $("btnLoadUtxos").onclick = loadUtxos;
  $("btnClearUtxos").onclick = () => { selectedOutpoints.clear(); renderUtxos(); };
  $("btnAddWatch").onclick = addWatchAddress;
  $("btnRefreshWatch").onclick = renderWatchlist;
  $("btnExportContacts").onclick = exportContactsPlain;
  $("btnExportContactsEncrypted").onclick = exportContactsEncrypted;
  $("contactsImportFile").onchange = (e) => importContactsFile(e.target.files?.[0]);
  $("btnCopyDescriptor").onclick = () => navigator.clipboard?.writeText($("walletDescriptor").value || "");
  $("btnImportDescriptor").onclick = importDescriptorToWatchlist;
  $("btnMakePsbt").onclick = makeUnsignedPsbt;
  if ($("btnWalletStatement")) $("btnWalletStatement").onclick = createWalletStatement;
  if ($("btnWalletStatementCsv")) $("btnWalletStatementCsv").onclick = downloadWalletStatementCsv;
  if ($("btnWalletStatementPdf")) $("btnWalletStatementPdf").onclick = downloadWalletStatementPdf;
  if ($("btnSaveBalanceAlert")) $("btnSaveBalanceAlert").onclick = saveBalanceAlertRule;
  if ($("btnEvaluateAlerts")) $("btnEvaluateAlerts").onclick = evaluateBalanceAlerts;
  if ($("btnSaveSpendingLimits")) $("btnSaveSpendingLimits").onclick = saveSpendingLimits;
  if ($("btnMarkBackupDone")) $("btnMarkBackupDone").onclick = markBackupVerified;
  $("contactSelect").onchange = useSelectedContact;
  $("btnUseContact").onclick = useSelectedContact;
  $("btnSaveContact").onclick = saveCurrentRecipientAsContact;
  $("btnDeleteContact").onclick = deleteSelectedContact;
  $("toAddr").oninput = syncContactNameFromAddress;
  renderContacts();
  renderWatchlist();
  $("btnMax").onclick = () => {
    try {
      $("amount").value = satsToInput(Math.max(0, lastSpendableSats - currentFeeSats()));
      $("sendMsg").textContent = "";
    } catch (e) {
      $("sendMsg").className = "err";
      $("sendMsg").textContent = "Failed: " + e.message;
    }
  };
  $("btnConsolidateSelf").onclick = () => {
    try {
      if (!state?.address) throw new Error("unlock a wallet first");
      $("toAddr").value = state.address;
      $("amount").value = satsToInput(Math.max(0, lastSpendableSats - currentFeeSats()));
      $("sendMsg").className = "muted";
      $("sendMsg").textContent = "Prepared a max self-send. Review it before broadcasting; mine one block after sending to confirm the consolidation.";
      syncContactNameFromAddress();
    } catch (e) {
      $("sendMsg").className = "err";
      $("sendMsg").textContent = "Failed: " + e.message;
    }
  };
  function estimateTxVbytes(inputCount, outputCount) {
    return Math.max(120, 10 + Number(inputCount || 1) * 68 + Number(outputCount || 2) * 31);
  }
  function simulateWalletRisk(to, amt, fee, selected) {
    const autoInputs = selected.length ? selected : lastUtxos.slice().sort((a, b) => Number(b.amount || 0) - Number(a.amount || 0));
    const used = [];
    let inputTotal = 0;
    for (const coin of autoInputs) {
      if (!selected.length && inputTotal >= amt + fee) break;
      used.push(coin);
      inputTotal += Number(coin.amount || 0);
    }
    const change = inputTotal - amt - fee;
    const vbytes = estimateTxVbytes(Math.max(1, used.length), change > 0 ? 2 : 1);
    const feeRate = fee / vbytes;
    const warnings = [];
    let decision = "allow";
    if (inputTotal < amt + fee) { decision = "block"; warnings.push("Selected or available coins do not cover amount + fee."); }
    if (feeRate > 250) { decision = decision === "block" ? "block" : "review"; warnings.push("Fee rate is unusually high."); }
    if (change > 0 && change < 546) { decision = decision === "block" ? "block" : "review"; warnings.push("Change output would be dust-sized."); }
    if (used.length > 50) { decision = decision === "block" ? "block" : "review"; warnings.push("This spend uses many UTXOs; consolidate first if possible."); }
    if (lastSpendableSats && amt + fee > lastSpendableSats * 0.8) { decision = decision === "block" ? "block" : "review"; warnings.push("This spend empties most of the wallet."); }
    if (sameAddress(to, state.address)) warnings.push("Recipient is your own wallet; this looks like consolidation.");
    const balanceAfter = Math.max(0, Number(lastSpendableSats || 0) - amt - fee);
    return { decision, warnings, inputTotal, change, vbytes, feeRate, inputCount: used.length, balanceAfter };
  }
  function renderRiskSimulation(risk) {
    const panel = $("riskPanel");
    if (!panel) return;
    panel.classList.remove("hide");
    $("riskDecision").textContent = risk.decision.toUpperCase();
    $("riskBalanceAfter").textContent = satsToInput(risk.balanceAfter) + " NET";
    $("riskChange").textContent = satsToInput(Math.max(0, risk.change)) + " NET";
    $("riskInputs").textContent = `${risk.inputCount} input(s), ${risk.vbytes} vbytes est.`;
    $("riskFeeRate").textContent = `${risk.feeRate.toFixed(2)} sats/vB`;
    const list = $("riskWarnings");
    list.innerHTML = "";
    const warnings = risk.warnings.length ? risk.warnings : ["No major wallet-risk warnings detected."];
    for (const warning of warnings) {
      const li = document.createElement("li");
      li.textContent = warning;
      list.appendChild(li);
    }
  }

  async function reviewSend() {
    const msg = $("sendMsg"); msg.className = ""; msg.textContent = "";
    try {
      const to = normalizeRecipientField();
      W.addressToScriptPubkey(to); // validates it's a v0 net1 address
      const amt = netToSats($("amount").value);
      const fee = netToSats($("fee").value);
      if (lastSpendableSats && amt + fee > lastSpendableSats) {
        throw new Error(`amount + fee is too high. Max send is ${satsToInput(Math.max(0, lastSpendableSats - fee))} NET with this fee.`);
      }
      if (!lastUtxos.length) await loadUtxos();
      const coinProblem = selectedUtxos().length ? "" : describeCoinSelectionProblem(amt, fee);
      if (coinProblem) {
        throw new Error(coinProblem);
      }
      const selected = selectedUtxos();
      if (selected.length) {
        const selectedTotal = selected.reduce((sum, u) => sum + Number(u.amount || 0), 0);
        if (selectedTotal < amt + fee) throw new Error("selected UTXOs do not cover amount + fee");
      }
      const risk = simulateWalletRisk(to, amt, fee, selected);
      renderRiskSimulation(risk);
      await checkSpendingLimits(amt, fee);
      const contact = contactForAddress(to);
      const warnings = [...risk.warnings.map((w) => "⚠ " + w)];
      // Address-poisoning check: a recipient that looks like a known address but
      // is not that address is the classic lookalike scam pattern.
      const known = [
        ...loadContacts().map((c) => ({ address: c.address, label: `contact “${c.name}”` })),
        ...loadWatchlist().map((w) => ({ address: w.address, label: `watch-only “${w.label || shortAddress(w.address)}”` })),
        { address: state.address, label: "your own address" },
      ];
      for (const k of known) {
        if (sameAddress(k.address, to)) continue;
        const a = String(k.address).toLowerCase(); const b = to.toLowerCase();
        if (a.slice(0, 12) === b.slice(0, 12) && a.slice(-5) === b.slice(-5)) {
          warnings.push(`⚠ This address looks similar to ${k.label} but is NOT the same address. Lookalike addresses are a common payment scam — verify every character before sending.`);
          break;
        }
      }
      if (lastSpendableSats && amt + fee > lastSpendableSats / 2) {
        warnings.push("⚠ Large send: this transaction spends more than half of your spendable balance.");
      }
      const warnBox = $("reviewWarning");
      if (warnBox) {
        warnBox.textContent = warnings.join(" ");
        warnBox.classList.toggle("hide", !warnings.length);
      }
      pendingSend = { to, amt, fee, outpoints: selected.map(outpointOf), blocked: risk.decision === "block", risk, contactName: contact?.name || "" };
      $("reviewTo").textContent = to;
      $("reviewContact").textContent = contact ? contact.name : "—";
      $("reviewAmount").textContent = satsToInput(amt) + " NET";
      $("reviewFee").textContent = satsToInput(fee) + " NET";
      $("reviewTotal").textContent = satsToInput(amt + fee) + " NET";
      $("reviewUtxos").textContent = selected.length ? `${selected.length} selected (${satsToInput(selected.reduce((sum, u) => sum + Number(u.amount || 0), 0))} NET)` : "Automatic coin selection";
      $("btnConfirmSend").disabled = risk.decision === "block";
      $("btnConfirmSend").textContent = risk.decision === "block" ? "Blocked by risk check" : "Send now";
      $("sendReview").classList.remove("hide");
    } catch (e) { msg.className = "err"; msg.textContent = "Failed: " + e.message; }
  }


  async function refreshWalletWorkflowStatus() {
    const msg = $("walletWorkflowMsg");
    if (!msg) return;
    try {
      const status = await api("/wallet/workflow");
      const presets = Object.keys(status.fee_presets || {}).join(" / ");
      msg.textContent = `Workflow: drafts ${(status.drafts||[]).length} · approvals ${(status.approvals||[]).length} · fee presets ${presets || "ready"} · offline signing ${status.offline_signing?.unsigned_export ? "ready" : "review"}.`;
      msg.className = "muted";
    } catch (e) {
      msg.textContent = "Workflow status unavailable: " + e.message;
      msg.className = "muted";
    }
  }

  async function savePendingDraft() {
    const msg = $("sendMsg");
    if (!pendingSend) { msg.className = "err"; msg.textContent = "Review the transaction before saving a draft."; return; }
    try {
      const draft = await api("/wallet/drafts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: pendingSend.to, amount: satsToInput(pendingSend.amt), fee: satsToInput(pendingSend.fee), memo: "browser wallet draft" }) });
      msg.className = "ok"; msg.textContent = "Saved draft " + (draft.draft_id || "ready") + ".";
      refreshWalletWorkflowStatus();
    } catch (e) { msg.className = "err"; msg.textContent = "Could not save draft: " + e.message; }
  }

  async function exportPendingUnsigned() {
    const msg = $("sendMsg");
    if (!pendingSend) { msg.className = "err"; msg.textContent = "Review the transaction before exporting."; return; }
    try {
      const payload = { magic: "netcoin-unsigned-send-v1", to: pendingSend.to, amount_sats: pendingSend.amt, fee_sats: pendingSend.fee, outpoints: pendingSend.outpoints || [], created_at: new Date().toISOString(), risk: pendingSend.risk || {} };
      downloadText("netcoin-unsigned-send.json", JSON.stringify(payload, null, 2));
      msg.className = "ok"; msg.textContent = "Unsigned transaction request exported for offline signing.";
    } catch (e) { msg.className = "err"; msg.textContent = "Export failed: " + e.message; }
  }

  $("btnSend").onclick = reviewSend;
  if ($("btnSaveDraft")) $("btnSaveDraft").onclick = savePendingDraft;
  if ($("btnExportUnsigned")) $("btnExportUnsigned").onclick = exportPendingUnsigned;
  refreshWalletWorkflowStatus();
  $("btnCancelSend").onclick = () => { pendingSend = null; $("sendReview").classList.add("hide"); };
  $("btnConfirmSend").onclick = async () => {
    const msg = $("sendMsg");
    if (!pendingSend) { msg.className = "err"; msg.textContent = "Review the transaction first."; return; }
    if (pendingSend.blocked) { msg.className = "err"; msg.textContent = "Blocked by wallet risk simulator. Adjust amount, fee, or coins."; return; }
    msg.className = ""; msg.textContent = "Sending…";
    try {
      const sent = pendingSend;
      const txid = await send(sent.to, sent.amt, sent.fee, sent.outpoints || []);
      recordSentTxMeta(txid, sent.to, sent.amt, sent.fee);
      await recordSpendForLimits(sent.amt, sent.fee);
      msg.className = "ok"; msg.textContent = sent.contactName ? `Sent to ${sent.contactName} ✓ txid ${txid.slice(0, 16)}…` : "Sent ✓ txid " + txid.slice(0, 16) + "…";
      pendingSend = null;
      $("sendReview").classList.add("hide");
      $("toAddr").value = ""; $("amount").value = ""; selectedOutpoints.clear(); renderUtxos(); setTimeout(refresh, 800);
    } catch (e) { msg.className = "err"; msg.textContent = "Failed: " + e.message; }
  };

  // ---------- boot ----------
  ensureWalletTabShell();
  applyWalletMode();
  renderProfiles();
  if (!resumeUnlockedSession()) show(hasProfiles() ? "unlock" : "welcome");
})();

/* Easier login: add a Show/Hide reveal toggle to every password field.
   Self-contained; runs after the main app and re-scans for fields added later. */
(function () {
  function addToggle(inp) {
    if (inp.dataset.pwToggle) return;
    inp.dataset.pwToggle = "1";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Show";
    btn.className = "secondary inline";
    btn.style.marginTop = "6px";
    btn.setAttribute("aria-label", "Show or hide password");
    btn.addEventListener("click", function () {
      const revealed = inp.type === "text";
      inp.type = revealed ? "password" : "text";
      btn.textContent = revealed ? "Show" : "Hide";
    });
    inp.insertAdjacentElement("afterend", btn);
  }
  function scan() { document.querySelectorAll('input[type="password"]').forEach(addToggle); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan);
  else scan();
  try { new MutationObserver(scan).observe(document.body, { childList: true, subtree: true }); } catch (e) {}
})();
