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
  const ADDR_TYPE_STORE = "ncw.addrType.v1";
  const UI_TAB_STORE = "ncw.walletTab.v1";
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
  let feeEstimatePayload = null;
  let lastRbfCandidate = null;
  let lastMultisigRedeemScript = "";

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const screens = ["welcome", "create", "restore", "privateKey", "unlock", "walletView"];
  function show(id) {
    screens.forEach((s) => $(s).classList.toggle("hide", s !== id));
    if (id === "walletView") applyPendingPrefill();
  }

  let prefillApplied = false;
  function applyPendingPrefill() {
    if (prefillApplied) return;
    const params = new URLSearchParams(location.search);
    if (params.get("buy_market")) { applyPendingMarketBuy(params); return; }
    let to = params.get("to") || "";
    let amt = params.get("amount") || "";
    const label = params.get("label") || "";
    const uri = params.get("uri");
    if (uri) {
      const parsed = parsePaymentUri(uri);
      if (parsed) { to = to || parsed.address; amt = amt || parsed.amount; }
    }
    if (!to) return;
    prefillApplied = true;
    ensureWalletTabShell();
    setActiveWalletTab("wallet");
    const activeSection = document.querySelector('.wallet-section[data-wallet-tab="wallet"]');
    if (activeSection) {
      const sendSection = $("wallet-send");
      if (sendSection) { document.querySelectorAll(".wallet-section.active-section").forEach((s) => s.classList.remove("active-section")); sendSection.classList.add("active-section"); }
    }
    if ($("toAddr")) $("toAddr").value = to;
    if (amt && $("amount")) $("amount").value = amt;
    if (label && $("contactName") && !$("contactName").value) $("contactName").value = label;
    validateRecipientField();
  }

  // ---- Markets deep link: Buy on markets.netcoin.online opens this wallet
  // with the order filled in, so signing happens where the key actually
  // lives instead of a "sign this order" step on a different origin. ----
  function canonicalizeForEnvelope(value) {
    if (Array.isArray(value)) return value.map(canonicalizeForEnvelope);
    if (value && typeof value === "object") {
      const out = {};
      for (const k of Object.keys(value).sort()) out[k] = canonicalizeForEnvelope(value[k]);
      return out;
    }
    return value;
  }
  async function marketOrderEnvelopeMessage(path, body, address) {
    const filtered = {};
    for (const k of Object.keys(body)) if (body[k] !== undefined && body[k] !== null) filtered[k] = body[k];
    const bodyStr = JSON.stringify(canonicalizeForEnvelope(filtered));
    const hashBuf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(bodyStr));
    const bodyHash = Array.from(new Uint8Array(hashBuf)).map((b) => b.toString(16).padStart(2, "0")).join("");
    const timestamp = Math.floor(Date.now() / 1000);
    const nonce = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    const message = ["NetCoin signed request", "netcoin-signed-envelope-v1", address, "POST", path, bodyHash, String(timestamp), nonce].join("\n");
    return { message, bodyHash, timestamp, nonce };
  }
  async function applyPendingMarketBuy(params) {
    prefillApplied = true;
    ensureWalletTabShell();
    if (!hasProfiles() && !resumeUnlockedSession()) { show("welcome"); return; }
    const marketId = params.get("buy_market");
    const outcomeId = params.get("buy_outcome") || "";
    const body = {
      outcome_id: outcomeId,
      side: params.get("buy_side") || "buy",
      order_type: params.get("buy_order_type") || "limit",
      time_in_force: params.get("buy_tif") || "GTC",
      quantity: Number(params.get("buy_qty") || 0),
      price_bps: params.get("buy_price_bps") ? Number(params.get("buy_price_bps")) : undefined,
      trader_address: state ? state.address : "",
    };
    // Developer is an admin-only tab; force admin view since arriving here
    // via a buy link means the user explicitly wants it.
    try { localStorage.setItem("nc.viewLevel.v1", "admin"); document.body.dataset.ncView = "admin"; } catch { /* ignore */ }
    setActiveWalletTab("developer");
    const box = $("marketBuyPanel");
    if (!box) return;
    box.classList.remove("hide");
    box.innerHTML = `<h3>Buy from Markets</h3>
      <p class="muted">Market <span class="mono">${esc(marketId)}</span> &middot; outcome <span class="mono">${esc(outcomeId)}</span> &middot; ${esc(body.quantity)} shares${body.price_bps ? " @ " + esc(body.price_bps / 100) + "&cent;" : " (market price)"}</p>
      <p class="muted">Using your wallet address <span class="mono">${esc(state ? state.address : "")}</span>.</p>
      <label>1. Sign this exact text</label>
      <textarea id="marketBuyMsgOut" class="mono" rows="4" readonly></textarea>
      <button type="button" class="secondary" id="btnCopyMarketBuyMsg">Copy message</button>
      <label style="margin-top:10px">Using the CLI</label>
      <pre class="mono" id="marketBuyCliCmd"></pre>
      <button type="button" class="secondary" id="btnCopyMarketBuyCli">Copy command</button>
      <label style="margin-top:10px">2. Paste the resulting signature</label>
      <input id="marketBuySigInput" class="mono" placeholder="base64 signature from signmessage output" autocomplete="off" />
      <button id="btnSubmitMarketBuy" type="button">Submit order</button>
      <p id="marketBuyMsg" class="muted" role="status" aria-live="polite" aria-atomic="true"></p>`;
    const path = `/markets/${encodeURIComponent(marketId)}/order`;
    const envelope = await marketOrderEnvelopeMessage(path, body, state.address);
    $("marketBuyMsgOut").value = envelope.message;
    $("marketBuyCliCmd").textContent = `python -m netcoin signmessage --wallet your-wallet.json --message "${envelope.message.replace(/"/g, '\\"')}"`;
    $("btnCopyMarketBuyMsg").onclick = () => navigator.clipboard.writeText(envelope.message).catch(() => {});
    $("btnCopyMarketBuyCli").onclick = () => navigator.clipboard.writeText($("marketBuyCliCmd").textContent).catch(() => {});
    $("btnSubmitMarketBuy").onclick = async () => {
      const sig = ($("marketBuySigInput").value || "").trim();
      if (!sig) { $("marketBuyMsg").className = "err"; $("marketBuyMsg").textContent = "Paste a signature first."; return; }
      $("marketBuyMsg").textContent = "Submitting…";
      try {
        const result = await api(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...body, signed_envelope: { address: state.address, method: "POST", path, body_hash: envelope.bodyHash, timestamp: envelope.timestamp, nonce: envelope.nonce, signature: sig } }),
        });
        $("marketBuyMsg").className = "ok";
        $("marketBuyMsg").textContent = `Order placed. Trades: ${(result.trades || []).length}.`;
      } catch (e) { $("marketBuyMsg").className = "err"; $("marketBuyMsg").textContent = "Failed: " + e.message; }
    };
  }
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
  const setAddressDisplay = (a) => {
    const el = $("addr"); if (el) { el.textContent = truncAddr(a); el.title = a || ""; }
    const settingsEl = $("settingsAddrOut"); if (settingsEl) settingsEl.textContent = a || "";
  };
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

  function friendlyWalletErrorMessage(error, context = "wallet") {
    const raw = String(error?.message || error || "unknown error").trim();
    if (/insufficient funds|amount \+ fee|selected UTXOs/i.test(raw)) {
      return `Balance or coin selection problem: ${raw}`;
    }
    if (/invalid address|scriptpubkey|recipient/i.test(raw)) {
      return `Recipient problem: ${raw}. Paste a full NetCoin address or a netcoin: payment link.`;
    }
    if (/non-JSON response|offline|failed to fetch|network/i.test(raw)) {
      return `Node connection problem: ${raw}. Refresh node status and try again on testnet.`;
    }
    if (/psbt|multisig|redeem/i.test(raw)) {
      return `${context} needs more signing data: ${raw}`;
    }
    return raw;
  }

  function markSendChecklist(risk, warnings) {
    const recipient = $("checkRecipient");
    const amountFee = $("checkAmountFee");
    const riskItem = $("checkRisk");
    const testnet = $("checkTestnet");
    if (!recipient || !amountFee || !riskItem || !testnet) return;
    recipient.className = "ok";
    amountFee.className = "ok";
    testnet.className = "ok";
    const blocked = risk?.decision === "block";
    riskItem.className = blocked || warnings.length ? "warn" : "ok";
    riskItem.textContent = blocked
      ? "Risk check blocked this send. Adjust amount, fee, or coins."
      : warnings.length
        ? "Risk warnings are present. Read them before sending."
        : "No blocking wallet risk warnings.";
  }

  function setWalletFlowStep(step) {
    const wallet = $("walletView");
    if (wallet) wallet.dataset.flowStep = step;
  }

  function setBackupMsg(text, className = "muted") {
    const msg = $("backupMsg");
    if (!msg) return;
    msg.className = className;
    msg.textContent = text;
  }

  // ---------- wallet tab shell and modes ----------
  const EVERYDAY = ["simple", "developer"];   // shown in both Simple and Admin views
  const ADMIN_ONLY = ["developer"];            // shown only in Admin view
  const WALLET_TABS = [
    { id: "wallet", label: "Wallet", modes: EVERYDAY },
    { id: "activity", label: "Activity", modes: EVERYDAY },
    { id: "mining", label: "Mining", modes: EVERYDAY },
    { id: "advanced", label: "Advanced", modes: ADMIN_ONLY },
    { id: "tokens", label: "Tokens", modes: ADMIN_ONLY },
    { id: "reports", label: "Reports", modes: ADMIN_ONLY },
    { id: "watch", label: "Watch-only", modes: ADMIN_ONLY },
    { id: "escrow", label: "Escrow", modes: ADMIN_ONLY },
    { id: "developer", label: "Developer", modes: ADMIN_ONLY },
    { id: "settings", label: "Settings", modes: EVERYDAY },
  ];
  const MODE_INFO = {
    simple: "Everyday wallet: balance, send, receive, activity, mining, and settings.",
    developer: "Full admin view: adds tokens, reports, watch-only, escrow, PSBT/multisig, and developer tools.",
  };
  // The wallet no longer has its own mode selector. It follows the site-wide
  // Admin/Simple (user) view toggle: Simple = everyday tabs, Admin = everything.
  function walletViewIsAdmin() {
    try {
      const v = (document.body.dataset.ncView || localStorage.getItem("nc.viewLevel.v1") || "simple").toLowerCase();
      return v === "admin";
    } catch (e) { return false; }
  }
  function walletUiMode() { return walletViewIsAdmin() ? "developer" : "simple"; }
  // Legacy shim: kept so older call sites don't break; view is driven by the site toggle now.
  function setWalletUiMode() { applyWalletMode(); }
  // Re-render wallet tabs whenever the site Admin/Simple toggle flips body[data-nc-view].
  (function observeSiteView() {
    try {
      const obs = new MutationObserver(() => applyWalletMode());
      obs.observe(document.body, { attributes: true, attributeFilter: ["data-nc-view"] });
    } catch (e) {}
  })();
  function activeWalletTab() {
    const tab = localStorage.getItem(UI_TAB_STORE) || "wallet";
    // Legacy sub-tab ids collapse into the Wallet tab. "activity" is now its own tab.
    return ["overview", "send", "receive", "contacts"].includes(tab) ? "wallet" : tab;
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
      // Keep the Wallet tab minimal: balance+address overview, Receive, and Send.
      // Everything else moves to its own tab so the page stops being one long stack.
      let tab = "advanced";
      if (card.classList.contains("wallet-overview-card")) { tab = "wallet"; card.id = card.id || "wallet-home"; }
      else if (card.querySelector("#receiveOut")) { tab = "wallet"; card.id = card.id || "wallet-receive"; }
      else if (card.querySelector("#btnSend")) { tab = "wallet"; card.id = card.id || "wallet-send"; }
      else if (card.querySelector("#txHistory")) { tab = "activity"; card.id = card.id || "wallet-activity"; }
      else if (["speedUpCard", "psbtToolsCard", "multisigToolsCard"].includes(card.id)) tab = "advanced";
      else if (card.classList.contains("wallet-availability-card")) tab = "wallet";
      else if (card.querySelector("#contactsImportFile")) { tab = "settings"; card.id = card.id || "wallet-settings-backups"; }
      else if (card.querySelector("#statementOut")) tab = "reports";
      else if (card.querySelector("#walletDescriptor")) tab = "advanced";
      else if (card.querySelector("#watchList")) tab = "watch";
      card.classList.add("wallet-section");
      card.dataset.walletTab = tab;
    }

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
      <p class="muted">2-of-3 escrow: funds go to an address that needs 2 of buyer/seller/mediator signatures to release or refund. Type usernames if the other parties have one registered &mdash; no need to know raw pubkeys.</p>
      <div class="row compact-row">
        <input id="escrowBuyerPub" class="mono" placeholder="Buyer: username or pubkey hex" autocomplete="off" />
        <input id="escrowSellerPub" class="mono" placeholder="Seller: username or pubkey hex" autocomplete="off" />
      </div>
      <div class="row compact-row">
        <input id="escrowMediatorPub" class="mono" placeholder="Mediator: username or pubkey hex" autocomplete="off" />
        <input id="escrowAmount" inputmode="decimal" placeholder="Amount (NET)" autocomplete="off" />
      </div>
      <label for="escrowTerms">Terms, optional</label>
      <textarea id="escrowTerms" placeholder="What this escrow is for"></textarea>
      <button id="btnCreateEscrow" type="button">Create escrow</button>
      <p id="escrowMsg" class="muted" role="status" aria-live="polite" aria-atomic="true"></p>
      <h3 style="margin-top:16px">Your escrows</h3>
      <button id="btnLoadMyEscrows" class="secondary" type="button">Refresh my escrows</button>
      <div id="myEscrowList" class="watch-list"><span class="muted">Unlock the wallet, then refresh to see escrows you're part of.</span></div>
      <div class="row compact-row" style="margin-top:10px">
        <input id="escrowLookupId" class="mono" placeholder="Or load by escrow_id" autocomplete="off" />
        <button id="btnLoadEscrow" class="secondary inline" type="button">Load</button>
      </div>
      <div id="escrowDetail" class="review hide">
        <div class="kv">
          <div class="k">Address</div><div class="v mono" id="escrowAddr"></div>
          <div class="k">Status</div><div class="v" id="escrowStatus"></div>
          <div class="k">Amount</div><div class="v" id="escrowAmountOut"></div>
        </div>
        <p class="muted" id="escrowNextAction"></p>
        <div id="escrowActionButtons" class="row compact-row"></div>
      </div>`, "escrow"));
    addWalletSection(walletSection("Developer", `
      <div id="marketBuyPanel" class="review hide"></div>
      <p class="muted">Payment links, developer API keys, webhooks, reward simulations, and app-layer contract templates &mdash; using this wallet's own address as the developer identity. No separate site or ID needed.</p>
      <label for="devPaymentAmount">Create a payment link</label>
      <div class="row compact-row">
        <input id="devPaymentAmount" inputmode="decimal" placeholder="Amount (NET)" autocomplete="off" />
        <input id="devPaymentTitle" placeholder="Title, e.g. Starter pack" autocomplete="off" />
      </div>
      <button id="btnCreatePaymentLink" type="button">Create payment link</button>
      <pre id="devPaymentOut" class="mono muted">Link appears here.</pre>
      <label for="devApiKeyLabel" style="margin-top:10px">Create a developer API key</label>
      <button id="btnCreateDevApiKey" class="secondary" type="button">Create API key</button>
      <div id="devApiKeyOut" class="review hide">
        <div class="row compact-row"><input id="devApiKeyField" class="mono" readonly /><button id="btnCopyDevApiKey" class="secondary inline" type="button">Copy</button></div>
        <p class="muted">Shown once. Store it somewhere safe.</p>
      </div>
      <label for="devWebhookUrl" style="margin-top:10px">Register a webhook</label>
      <input id="devWebhookUrl" placeholder="https://example.com/netcoin/webhook" autocomplete="off" />
      <button id="btnRegisterDevWebhook" class="secondary" type="button">Register webhook</button>
      <p id="devWebhookMsg" class="muted"></p>
      <h3 style="margin-top:16px">Contract templates</h3>
      <button id="btnLoadContractTemplates" class="secondary" type="button">Load templates</button>
      <div id="contractTemplateList" class="watch-list"><span class="muted">Load templates to see available contract types.</span></div>
      <p class="muted"><a href="https://developers.netcoin.online/console.html">Full Developer Console</a> and <a href="https://api.netcoin.online/">API docs</a> for advanced use.</p>`, "developer"));

    const settings = walletSection("Settings", `
      <p class="muted">Manage this wallet's session and backups. Use the site's <b>Simple / Admin</b> toggle (bottom-left) to switch between the everyday wallet and the full toolset — Admin adds Tokens, Payments, Reports, Watch-only, Escrow, PSBT/multisig, and developer tools.</p>
      <label for="sessionAutoLock">Session auto-lock</label>
      <select id="sessionAutoLock" aria-label="Session auto-lock timeout">
        <option value="15">15 minutes</option>
        <option value="30">30 minutes</option>
        <option value="60">1 hour</option>
        <option value="120">2 hours</option>
        <option value="0">Disabled for this tab</option>
      </select>
      <p id="sessionAutoLockStatus" class="muted auto-lock-status"></p>
      <h3 style="margin-top:16px">Related tools</h3>
      <div class="section-links">
        <a href="https://pay.netcoin.online/"><b>Payment hub</b><br><span class="muted">Checkout, receipts, tips, donations, and profiles.</span></a>
        <a href="https://merchant.netcoin.online/"><b>Merchant dashboard</b><br><span class="muted">Invoices, POS, refunds, API keys, webhooks, and exports.</span></a>
      </div>`, "settings");
    addWalletSection(settings);

    addWalletSection(walletSection("Your address", `
      <p class="muted">Your address is your identity. Optionally attach a username so people can find you by name instead &mdash; on the leaderboard, tip/donate pages, and public profiles at <span class="mono">community.netcoin.online/u/&lt;username&gt;</span>.</p>
      <label class="muted">This wallet's address</label>
      <pre id="settingsAddrOut" class="mono muted"></pre>
      <label for="usernameInput">Attach a username, optional</label>
      <input id="usernameInput" placeholder="letters, numbers, dash, underscore" autocomplete="off" />
      <label for="usernameDisplay">Display name, optional</label>
      <input id="usernameDisplay" placeholder="Shown instead of the raw username" autocomplete="off" />
      <button id="btnRegisterUsername" type="button">Save username for this wallet</button>
      <p id="usernameMsg" class="muted" role="status" aria-live="polite" aria-atomic="true"></p>
      <h3 style="margin-top:16px">Look up any username</h3>
      <p class="muted">Check whether a username is tied to a NetCoin address. Works anywhere someone can be tipped, paid, or added to escrow.</p>
      <div class="row compact-row">
        <input id="usernameLookup" placeholder="username" autocomplete="off" />
        <button id="btnLookupUsername" class="secondary inline" type="button">Look up</button>
      </div>
      <pre id="usernameLookupOut" class="mono muted">Address appears here.</pre>`, "settings"));
  }
  function applyWalletMode() {
    const wallet = $("walletView");
    if (!wallet) return;
    ensureWalletTabShell();
    syncAutoLockControls();
    const mode = walletUiMode();
    let tab = activeWalletTab();
    if (!tabAllowed(tab, mode)) tab = "wallet";
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
      // Payment intent lets an offline copy of this wallet reconstruct and sign
      // the exact same payment; the outputs are re-verified on import so a
      // tampered signer cannot change where funds go.
      const intent = {
        utxos: chosen.map((u) => ({ txid: u.txid, vout: u.vout, amount: u.amount, address: u.address || state.address })),
        toAddress: to,
        amount,
        fee,
        changeAddress: state.address,
      };
      const psbt = {
        magic: "netcoin-psbt-v1",
        tx,
        prevouts,
        intent,
        intent_hash: await psbtIntentHash(intent),
        created_at: new Date().toISOString(),
        note: "Unsigned browser wallet PSBT. Review offline before signing.",
      };
      const encoded = encodeNetPsbt(psbt);
      lastUnsignedPsbt = encoded;
      $("psbtOut").value = encoded;
      renderPsbtQr(encoded);
      $("btnDownloadUnsignedPsbt")?.removeAttribute("disabled");
      $("btnSignPsbtOffline")?.removeAttribute("disabled");
      setDescriptorMsg("Unsigned PSBT created. Export it (file/QR) to an offline signer, or sign here.", "ok");
    } catch (e) {
      setDescriptorMsg("PSBT creation failed: " + e.message, "err");
    }
  }

  // ---------- airgap / offline PSBT signing loop ----------
  const PSBT_SIGNED_PREFIX = "netpsbt-signed:";
  let lastUnsignedPsbt = "";
  let pendingSignedPsbt = null; // { intent, signed } awaiting broadcast

  async function psbtIntentHash(intent) {
    const canonical = JSON.stringify({
      utxos: intent.utxos, toAddress: intent.toAddress, amount: intent.amount,
      fee: intent.fee, changeAddress: intent.changeAddress,
    });
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical));
    return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  function decodePsbt(text, prefix) {
    const t = String(text || "").trim();
    if (!t.startsWith(prefix)) throw new Error("expected a " + prefix.replace(":", "") + " payload");
    return JSON.parse(atob(t.slice(prefix.length)));
  }

  // Sign an unsigned PSBT in this browser using the loaded key (software offline
  // signer). On a real airgapped device this same wallet copy holds the key.
  async function signPsbtOffline() {
    try {
      if (!state) throw new Error("unlock a wallet first");
      const unsigned = decodePsbt($("psbtOut").value || lastUnsignedPsbt, "netpsbt:");
      if (unsigned.magic !== "netcoin-psbt-v1" || !unsigned.intent) throw new Error("not a NetCoin unsigned PSBT with a payment intent");
      const intent = unsigned.intent;
      if ((await psbtIntentHash(intent)) !== unsigned.intent_hash) throw new Error("PSBT intent hash mismatch; refusing to sign a tampered payment");
      const signed = W.buildSignedPayment({
        privHex: state.privHex, utxos: intent.utxos, toAddress: intent.toAddress,
        amount: intent.amount, fee: intent.fee, changeAddress: intent.changeAddress, maxInputs: MAX_WALLET_SEND_INPUTS,
      });
      const wrapper = { magic: "netcoin-psbt-signed-v1", intent, intent_hash: unsigned.intent_hash, signed, signed_at: new Date().toISOString() };
      const encoded = PSBT_SIGNED_PREFIX + btoa(JSON.stringify(wrapper));
      $("signedPsbtOut").value = encoded;
      renderPsbtQr(encoded);
      $("btnDownloadSignedPsbt")?.removeAttribute("disabled");
      setDescriptorMsg("Signed offline. Export the signed PSBT back to the online wallet to broadcast.", "ok");
    } catch (e) {
      setDescriptorMsg("Offline signing failed: " + e.message, "err");
    }
  }

  // Import a signed PSBT, re-verify its payment matches the intent, and stage it.
  async function importSignedPsbt(rawText) {
    try {
      const wrapper = decodePsbt(rawText, PSBT_SIGNED_PREFIX);
      if (wrapper.magic !== "netcoin-psbt-signed-v1" || !wrapper.intent || !wrapper.signed) throw new Error("not a NetCoin signed PSBT");
      if ((await psbtIntentHash(wrapper.intent)) !== wrapper.intent_hash) throw new Error("signed PSBT intent hash mismatch; refusing to broadcast a tampered payment");
      pendingSignedPsbt = wrapper;
      const i = wrapper.intent;
      const review = $("psbtReview");
      if (review) {
        review.innerHTML =
          `<div class="kv"><div class="k">To</div><div class="v mono">${esc(i.toAddress)}</div>` +
          `<div class="k">Amount</div><div class="v">${satsToNet(i.amount)} NET</div>` +
          `<div class="k">Fee</div><div class="v">${satsToNet(i.fee)} NET</div>` +
          `<div class="k">Inputs</div><div class="v">${i.utxos.length}</div></div>`;
        review.classList.remove("hide");
      }
      $("btnBroadcastSignedPsbt")?.removeAttribute("disabled");
      setDescriptorMsg("Signed PSBT verified against its intent. Review, then broadcast.", "ok");
    } catch (e) {
      pendingSignedPsbt = null;
      $("btnBroadcastSignedPsbt")?.setAttribute("disabled", "disabled");
      setDescriptorMsg("Signed PSBT import failed: " + e.message, "err");
    }
  }

  async function broadcastSignedPsbt() {
    try {
      if (!pendingSignedPsbt) throw new Error("import a signed PSBT first");
      const res = await api("/tx", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pendingSignedPsbt.signed) });
      setDescriptorMsg("Broadcast ✓ txid " + String(res.txid || "").slice(0, 16) + "…", "ok");
      pendingSignedPsbt = null;
      $("btnBroadcastSignedPsbt")?.setAttribute("disabled", "disabled");
      refresh();
    } catch (e) {
      setDescriptorMsg("Broadcast failed: " + e.message, "err");
    }
  }

  function hydrateRbfBumpCard() {
    if (!$("rbfOriginalTx")) return;
    if (lastRbfCandidate?.tx) $("rbfOriginalTx").value = JSON.stringify(lastRbfCandidate.tx, null, 2);
    if (lastRbfCandidate?.prevouts) $("rbfPrevouts").value = JSON.stringify(lastRbfCandidate.prevouts, null, 2);
    if (lastRbfCandidate?.feeSats && !$("rbfNewFee").value) $("rbfNewFee").value = satsToInput(Math.max(Number(lastRbfCandidate.feeSats) * 2, Number(lastRbfCandidate.feeSats) + 500));
    if (state?.address && !$("rbfChangeAddress").value) $("rbfChangeAddress").value = state.address;
  }

  function readJsonField(id, fallback) {
    const raw = ($(id)?.value || "").trim();
    if (!raw) return fallback;
    try { return JSON.parse(raw); }
    catch { throw new Error(`${id} must contain valid JSON`); }
  }

  async function bumpFeeFromCard() {
    const out = $("rbfBumpOut");
    try {
      const originalTx = readJsonField("rbfOriginalTx", lastRbfCandidate?.tx);
      const prevouts = readJsonField("rbfPrevouts", lastRbfCandidate?.prevouts);
      if (!originalTx) throw new Error("paste the original transaction JSON or use the last RBF send");
      if (!Array.isArray(prevouts) || !prevouts.length) throw new Error("paste the previous outputs JSON");
      const newFee = ($("rbfNewFee")?.value || "").trim();
      if (!newFee) throw new Error("enter a higher fee in NET");
      const changeAddress = ($("rbfChangeAddress")?.value || state?.address || "").trim();
      if (!changeAddress) throw new Error("enter a change address or unlock this wallet");
      const broadcast = Boolean($("rbfBroadcastNow")?.checked);
      const bumped = await api("/wallet/rbf-bump", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ original_tx: originalTx, prevouts, new_fee: newFee, change_address: changeAddress, broadcast }) });
      lastRbfCandidate = { ...lastRbfCandidate, tx: bumped.replacement_tx || bumped.tx, feeSats: bumped.new_fee, prevouts };
      if (out) {
        out.className = "mono ok";
        out.textContent = JSON.stringify({ broadcast, txid: bumped.txid || bumped.replacement_txid || null, old_fee: bumped.old_fee, new_fee: bumped.new_fee, replacement_tx: bumped.replacement_tx || bumped.tx }, null, 2);
      }
    } catch (e) {
      if (out) { out.className = "mono err"; out.textContent = "Fee bump failed: " + e.message; }
    }
  }

  async function bumpLastFee() {
    const msg = $("sendMsg");
    try {
      if (!lastRbfCandidate?.tx || !lastRbfCandidate?.prevouts) throw new Error("send an opt-in-RBF transaction first");
      hydrateRbfBumpCard();
      await bumpFeeFromCard();
      msg.className = "ok";
      msg.textContent = "Fee bump preview created in the Speed up transaction card.";
    } catch (e) {
      msg.className = "err";
      msg.textContent = "Fee bump failed: " + e.message;
    }
  }

  function setMultisigProgress(progress) {
    const msg = $("multisigProgress");
    if (!msg) return;
    const p = progress || {};
    msg.textContent = `${p.collected || 0} of ${p.required || 0} collected${p.ready ? " · ready to extract" : ""}.`;
  }

  async function createMultisigWallet() {
    const out = $("multisigCreateOut");
    try {
      const created = await api("/wallet/multisig/create", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ required: $("multisigRequired").value, pubkeys: $("multisigPubkeys").value }) });
      lastMultisigRedeemScript = created.redeem_script;
      out.textContent = JSON.stringify({ address: created.address, redeem_script: created.redeem_script }, null, 2);
    } catch (e) {
      out.textContent = "Multisig create failed: " + e.message;
    }
  }

  async function createMultisigSpend() {
    const out = $("multisigProgress");
    try {
      const created = await api("/wallet/multisig/psbt/create", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ redeem_script: lastMultisigRedeemScript, to: normalizeRecipientField(), amount: $("amount").value, fee: $("fee").value }) });
      $("multisigSpendPsbt").value = created.unsigned_psbt;
      setMultisigProgress(created.progress);
      out.className = "muted";
    } catch (e) {
      out.className = "err";
      out.textContent = "Multisig spend failed: " + e.message;
    }
  }

  async function signMultisigSpend() {
    const out = $("multisigProgress");
    try {
      const signed = await api("/wallet/multisig/psbt/sign", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ psbt: $("multisigSpendPsbt").value, redeem_script: lastMultisigRedeemScript }) });
      $("multisigSpendPsbt").value = signed.signed_psbt;
      setMultisigProgress(signed.progress);
      out.className = "muted";
    } catch (e) {
      out.className = "err";
      out.textContent = "Multisig signing failed: " + e.message;
    }
  }

  async function extractMultisigSpend() {
    const out = $("multisigProgress");
    try {
      const extracted = await api("/wallet/psbt/extract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ psbt: $("multisigSpendPsbt").value }) });
      setMultisigProgress(extracted.progress);
      out.className = "ok";
      out.textContent = "Extracted transaction " + String(extracted.txid || "").slice(0, 16) + "…";
    } catch (e) {
      out.className = "err";
      out.textContent = "Multisig extract failed: " + e.message;
    }
  }

  // Chunked animated QR so a large PSBT can cross an airgap by camera. Each
  // frame is "p<i>/<n>:<chunk>" and small enough for the bundled v1-5 renderer.
  let psbtQrTimer = null;
  function renderPsbtQr(text) {
    const canvas = $("psbtQrCanvas");
    if (!canvas) return;
    if (psbtQrTimer) { clearInterval(psbtQrTimer); psbtQrTimer = null; }
    if (!text) return;
    const CHUNK = 70; // keep each frame within the bundled v1-5 QR renderer's capacity
    const frames = [];
    const n = Math.ceil(text.length / CHUNK);
    for (let i = 0; i < n; i++) frames.push(`p${i + 1}/${n}:${text.slice(i * CHUNK, (i + 1) * CHUNK)}`);
    let idx = 0;
    const ctx = canvas.getContext("2d");
    const draw = () => {
      try {
        const matrix = makeQrMatrix(frames[idx % frames.length]);
        const quiet = 4;
        const scale = Math.floor(canvas.width / (matrix.length + quiet * 2));
        const used = (matrix.length + quiet * 2) * scale;
        const off = Math.floor((canvas.width - used) / 2);
        ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#000";
        for (let y = 0; y < matrix.length; y++) for (let x = 0; x < matrix.length; x++) {
          if (matrix[y][x]) ctx.fillRect(off + (x + quiet) * scale, off + (y + quiet) * scale, scale, scale);
        }
        const label = $("psbtQrLabel"); if (label) label.textContent = `Airgap QR frame ${(idx % frames.length) + 1}/${frames.length}`;
        idx++;
      } catch { /* frame too large for bundled renderer; file export still works */ }
    };
    draw();
    if (frames.length > 1) psbtQrTimer = setInterval(draw, 700);
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

  async function registerUsername() {
    const msg = $("usernameMsg");
    if (!state) { msg.className = "err"; msg.textContent = "Unlock the wallet first."; return; }
    const username = ($("usernameInput").value || "").trim();
    if (!username) { msg.className = "err"; msg.textContent = "Enter a username."; return; }
    try {
      const pubkey = W.walletFromPrivateKey(state.privHex).pubHex;
      const rec = await api("/usernames", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, address: state.address, pubkey, display_name: $("usernameDisplay").value || "" }),
      });
      msg.className = "ok";
      msg.textContent = `Saved: @${rec.username} now resolves to your address (and can be used in Escrow instead of a raw pubkey).`;
    } catch (e) { msg.className = "err"; msg.textContent = "Could not save username: " + e.message; }
  }

  async function resolveEscrowParty(input) {
    const raw = (input || "").trim();
    if (!raw) throw new Error("required");
    if (/^[0-9a-fA-F]{66}$/.test(raw)) return raw;
    const clean = raw.replace(/^@/, "");
    const rec = await api("/usernames/" + encodeURIComponent(clean));
    if (!rec.pubkey) throw new Error(`@${clean} has no pubkey on file yet (they need to re-save their username from a newer wallet)`);
    return rec.pubkey;
  }

  async function lookupUsername() {
    const out = $("usernameLookupOut");
    const name = ($("usernameLookup").value || "").trim();
    if (!name) { out.textContent = "Enter a username to look up."; return; }
    try {
      const rec = await api("/usernames/" + encodeURIComponent(name));
      out.textContent = `@${rec.username} -> ${rec.address}` + (rec.display_name ? ` (${rec.display_name})` : "");
    } catch (e) { out.textContent = "Not found: " + e.message; }
  }

  let lastEscrowId = "";
  async function createEscrow() {
    const msg = $("escrowMsg");
    try {
      const amount = parseFloat($("escrowAmount").value || "0");
      if (!(amount > 0)) throw new Error("amount must be greater than zero");
      const [buyer_pubkey, seller_pubkey, mediator_pubkey] = await Promise.all([
        resolveEscrowParty($("escrowBuyerPub").value),
        resolveEscrowParty($("escrowSellerPub").value),
        resolveEscrowParty($("escrowMediatorPub").value),
      ]);
      const rec = await api("/escrows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ buyer_pubkey, seller_pubkey, mediator_pubkey, amount, terms: $("escrowTerms").value || "" }),
      });
      lastEscrowId = rec.escrow_id;
      msg.className = "ok";
      msg.textContent = `Created escrow ${rec.escrow_id}. Fund the escrow address, then check "Your escrows" below.`;
      await loadMyEscrows();
      await loadEscrowById(rec.escrow_id);
    } catch (e) { msg.className = "err"; msg.textContent = "Could not create escrow: " + e.message; }
  }

  function escrowRole(rec) {
    if (!state) return null;
    try {
      const myPub = W.walletFromPrivateKey(state.privHex).pubHex;
      if (rec.buyer_pubkey === myPub) return "buyer";
      if (rec.seller_pubkey === myPub) return "seller";
      if (rec.mediator_pubkey === myPub) return "mediator";
    } catch { /* ignore */ }
    return null;
  }

  async function loadMyEscrows() {
    const box = $("myEscrowList");
    if (!state) { box.innerHTML = '<span class="muted">Unlock the wallet first.</span>'; return; }
    box.innerHTML = "Loading…";
    try {
      const myPub = W.walletFromPrivateKey(state.privHex).pubHex;
      const data = await api("/escrows");
      const mine = (data.escrows || []).filter((e) => [e.buyer_pubkey, e.seller_pubkey, e.mediator_pubkey].includes(myPub));
      box.innerHTML = mine.length
        ? mine.map((e) => `<div class="watch-item"><b>${esc(e.escrow_id)}</b><div class="muted">${esc(e.status)} · ${esc(e.amount)} NET · you are ${esc(escrowRole(e) || "?")}</div><button type="button" class="secondary smallbtn" data-load-escrow="${esc(e.escrow_id)}">Open</button></div>`).join("")
        : '<span class="muted">No escrows involve this wallet yet.</span>';
      box.querySelectorAll("[data-load-escrow]").forEach((btn) => btn.addEventListener("click", () => loadEscrowById(btn.dataset.loadEscrow)));
    } catch (e) { box.innerHTML = '<span class="err">Could not load escrows: ' + esc(e.message) + "</span>"; }
  }

  async function loadEscrowById(id) {
    if (!id) { $("escrowMsg").className = "err"; $("escrowMsg").textContent = "Enter an escrow_id to load."; return; }
    try {
      const rec = await api("/escrows/" + encodeURIComponent(id));
      lastEscrowId = rec.escrow_id;
      $("escrowDetail").classList.remove("hide");
      $("escrowAddr").textContent = rec.escrow_address;
      $("escrowStatus").textContent = rec.status;
      $("escrowAmountOut").textContent = rec.amount + " NET";
      renderEscrowNextAction(rec);
    } catch (e) { $("escrowMsg").className = "err"; $("escrowMsg").textContent = "Could not load escrow: " + e.message; }
  }
  function loadEscrow() { return loadEscrowById(($("escrowLookupId").value || lastEscrowId || "").trim()); }

  function renderEscrowNextAction(rec) {
    const role = escrowRole(rec);
    const next = $("escrowNextAction");
    const btns = $("escrowActionButtons");
    if (!role) {
      next.textContent = "You're not a party to this escrow (viewing read-only).";
      btns.innerHTML = "";
      return;
    }
    const actionsByStatus = {
      funding_ready: "Waiting for funds to arrive at the escrow address.",
      funded: "Funds are in. Approve release (pay the seller) or refund (return to buyer), or dispute.",
      pending_release: "Release requested — needs a second approval from another party.",
      pending_refund: "Refund requested — needs a second approval from another party.",
      released: "Released. Nothing more to do.",
      refunded: "Refunded. Nothing more to do.",
      disputed: "Disputed — the mediator should review and approve release or refund.",
      canceled: "Canceled.",
    };
    next.textContent = actionsByStatus[rec.status] || "";
    const canAct = ["funded", "pending_release", "pending_refund", "disputed"].includes(rec.status);
    btns.innerHTML = canAct
      ? '<button type="button" class="secondary inline" data-escrow-action="release">Approve release</button><button type="button" class="secondary inline" data-escrow-action="refund">Approve refund</button><button type="button" class="secondary inline" data-escrow-action="dispute">Dispute</button>'
      : "";
    btns.querySelectorAll("[data-escrow-action]").forEach((btn) => btn.addEventListener("click", () => submitEscrowAction(btn.dataset.escrowAction)));
  }

  async function submitEscrowAction(action) {
    const id = lastEscrowId;
    if (!id || !state) { $("escrowMsg").className = "err"; $("escrowMsg").textContent = "Load an escrow first."; return; }
    try {
      const signer = state.address;
      const rec = await api(`/escrows/${encodeURIComponent(id)}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, signer }),
      });
      $("escrowStatus").textContent = rec.status;
      $("escrowMsg").className = "ok";
      $("escrowMsg").textContent = `Recorded ${action}. Status: ${rec.status}`;
      renderEscrowNextAction(rec);
      loadMyEscrows();
    } catch (e) { $("escrowMsg").className = "err"; $("escrowMsg").textContent = "Could not submit action: " + e.message; }
  }

  async function loadContractTemplates() {
    const box = $("contractTemplateList");
    box.innerHTML = "Loading…";
    try {
      const data = await api("/contracts/templates");
      const items = Object.values(data.templates || data || {});
      box.innerHTML = items.length
        ? items.map((t) => `<div class="watch-item"><b>${esc(t.title || t.type || "")}</b><div class="muted">${esc(t.description || "")}</div></div>`).join("")
        : '<span class="muted">No templates available.</span>';
    } catch (e) { box.innerHTML = '<span class="err">Could not load templates: ' + esc(e.message) + "</span>"; }
  }

  async function createDevPaymentLink() {
    const out = $("devPaymentOut");
    if (!state) { out.textContent = "Unlock the wallet first."; return; }
    try {
      const amount = parseFloat($("devPaymentAmount").value || "0");
      if (!(amount > 0)) throw new Error("amount must be greater than zero");
      const rec = await api("/developer/payment-links", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ developer_id: state.address, address: state.address, amount, title: $("devPaymentTitle").value || "" }),
      });
      out.textContent = `https://pay.netcoin.online${rec.checkout_path}`;
    } catch (e) { out.textContent = "Failed: " + e.message; }
  }

  async function createDevApiKey() {
    const box = $("devApiKeyOut");
    if (!state) return;
    try {
      const rec = await api("/developer/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ developer_id: state.address }),
      });
      box.classList.remove("hide");
      $("devApiKeyField").value = rec.api_key;
    } catch (e) { $("devWebhookMsg").className = "err"; $("devWebhookMsg").textContent = "Failed: " + e.message; }
  }

  async function registerDevWebhook() {
    const msg = $("devWebhookMsg");
    if (!state) { msg.className = "err"; msg.textContent = "Unlock the wallet first."; return; }
    const url = ($("devWebhookUrl").value || "").trim();
    if (!url) { msg.className = "err"; msg.textContent = "Enter a webhook URL."; return; }
    try {
      await api("/developer/webhooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ developer_id: state.address, url }),
      });
      msg.className = "ok";
      msg.textContent = "Webhook registered.";
    } catch (e) { msg.className = "err"; msg.textContent = "Failed: " + e.message; }
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
    let data; let parsed = true;
    try { data = JSON.parse(text); } catch { parsed = false; data = {}; }
    if (!r.ok || data.error) {
      // A non-JSON body (nginx/proxy error pages, gateway timeouts) must never
      // be shown to the user verbatim — it can be an entire raw HTML page.
      const message = parsed ? (data.error || ("HTTP " + r.status)) : ("HTTP " + r.status + " (non-JSON response from node)");
      throw new Error(message);
    }
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
    const vsize = estimateVsize(nInputs);
    const nodePresets = feeEstimatePayload?.presets || {};
    const fromNode = (name, fallbackRate) => {
      const preset = nodePresets[name] || {};
      const rate = Number(preset.fee_rate_per_kvb || 0) / 1000;
      const direct = Number(preset.estimated_fee_sats || 0);
      if (rate > 0) return Math.max(FEE_FLOOR_SATS, Math.ceil(vsize * rate));
      if (direct > 0) return Math.max(FEE_FLOOR_SATS, Math.ceil((direct * vsize) / Number(feeEstimatePayload?.assumed_vbytes || 200)));
      return Math.max(FEE_FLOOR_SATS, Math.ceil(vsize * fallbackRate));
    };
    const slow = fromNode("slow", FEE_RATE_MIN_SATS_PER_VBYTE);
    const normal = fromNode("normal", FEE_RATE_MIN_SATS_PER_VBYTE * 10);
    const fast = fromNode("fast", FEE_RATE_MIN_SATS_PER_VBYTE * 100);
    return { slow, normal, fast, inputs: nInputs };
  }
  function updateFeePresetCards(tiers) {
    const labels = { slow: "feeSlowLabel", normal: "feeNormalLabel", fast: "feeFastLabel" };
    for (const [presetName, labelId] of Object.entries(labels)) {
      const label = $(labelId);
      if (label && tiers?.[presetName] != null) label.textContent = satsToInput(tiers[presetName]) + " NET";
    }
    const selected = $("feePreset")?.value || "normal";
    document.querySelectorAll("[data-fee-preset]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.feePreset === selected);
      btn.setAttribute("aria-pressed", btn.dataset.feePreset === selected ? "true" : "false");
    });
    const status = $("feePresetStatus");
    if (status) {
      const names = { slow: "Economy", normal: "Standard", fast: "Fast", custom: "Custom" };
      status.textContent = `${names[selected] || "Standard"} fee selected. Estimates refresh from the node when available.`;
    }
  }

  function chooseFeePreset(presetName) {
    const preset = $("feePreset");
    if (!preset || !["slow", "normal", "fast"].includes(presetName)) return;
    preset.value = presetName;
    const tiers = preset._tiers || autoFeeTiers(0);
    $("fee").value = satsToInput(tiers[presetName] ?? tiers.normal);
    updateFeePresetCards(tiers);
    updateFeeHint();
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
        `<option value="slow">Economy — ${satsToInput(t.slow)} NET</option>` +
        `<option value="normal">Standard — ${satsToInput(t.normal)} NET</option>` +
        `<option value="fast">Fast — ${satsToInput(t.fast)} NET</option>` +
        `<option value="custom">Custom</option>`;
      preset.value = sel === "slow" || sel === "fast" || sel === "custom" ? sel : "normal";
      preset._tiers = t;
      if (!wasCustom) $("fee").value = satsToInput(t[preset.value] ?? t.normal);
      updateFeePresetCards(t);
    }
    updateFeeHint();
  }
  async function updateFeeEstimates() {
    try { feeEstimatePayload = await api("/fee-estimates"); }
    catch { feeEstimatePayload = null; }
    refreshAutoFees(false);
  }

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
        return `<div class="review tx-row"><div class="tx-row-head"><strong>${esc(label || "Transaction")}</strong><span class="muted">${subtitle}</span></div><div class="mono txid-line">${esc(txid)}</div><div class="tx-actions"><a href="https://explorer.netcoin.online/tx.html?txid=${encodeURIComponent(txid)}" target="_blank" rel="noreferrer">Open in Explorer</a><button class="secondary inline btnCopyTxid" data-txid="${esc(txid)}" type="button">Copy txid</button></div><div class="row compact-row"><input data-txid="${esc(txid)}" class="txLabel" placeholder="Label this transaction" value="${esc(label)}" /><button class="secondary inline btnSaveTxLabel" data-txid="${esc(txid)}" type="button">Save</button></div></div>`;
      }).join("");
      document.querySelectorAll(".btnCopyTxid").forEach((btn) => {
        btn.onclick = async () => {
          await navigator.clipboard?.writeText(btn.dataset.txid || "");
          btn.textContent = "Copied";
          setTimeout(() => { btn.textContent = "Copy txid"; }, 900);
        };
      });
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
    const rbfInputs = W.selectCoins(utxos, amountSats + feeSats, MAX_WALLET_SEND_INPUTS).chosen;
    const signed = W.buildSignedPayment({
      privHex: state.privHex, utxos, toAddress, amount: amountSats, fee: feeSats, changeAddress: state.address, maxInputs: MAX_WALLET_SEND_INPUTS, rbf: Boolean($("rbfOptIn")?.checked),
    });
    lastRbfCandidate = $("rbfOptIn")?.checked ? {
      tx: signed,
      feeSats,
      prevouts: rbfInputs.map((u) => ({ txid: u.txid, vout: u.vout, height: null, coinbase: false, output: { amount: u.amount, address: u.address || state.address, script_pubkey: u.script_pubkey || W.addressToScriptPubkey(u.address || state.address) } })),
    } : null;
    hydrateRbfBumpCard();
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
  $("fee").oninput = () => { $("feePreset").value = "custom"; updateFeePresetCards($("feePreset")._tiers || autoFeeTiers(0)); updateFeeHint(); };
  $("feePreset").onchange = () => {
    const p = $("feePreset");
    if (p.value !== "custom") {
      const tiers = p._tiers || autoFeeTiers(0);
      $("fee").value = satsToInput(tiers[p.value] ?? tiers.normal);
      updateFeePresetCards(tiers);
      updateFeeHint();
    } else {
      updateFeePresetCards(p._tiers || autoFeeTiers(0));
    }
  };
  document.addEventListener("click", (ev) => {
    const feeButton = ev.target?.closest?.("[data-fee-preset]");
    if (feeButton) chooseFeePreset(feeButton.dataset.feePreset);
  });
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
  $("btnDownloadUnsignedPsbt").onclick = () => downloadText("netcoin-unsigned.psbt", $("psbtOut").value || lastUnsignedPsbt, "text/plain");
  $("btnSignPsbtOffline").onclick = signPsbtOffline;
  $("btnDownloadSignedPsbt").onclick = () => downloadText("netcoin-signed.psbt", $("signedPsbtOut").value, "text/plain");
  $("btnImportSignedPsbt").onclick = () => importSignedPsbt($("signedPsbtOut").value);
  $("btnBroadcastSignedPsbt").onclick = broadcastSignedPsbt;
  if ($("btnUseLastRbfCandidate")) $("btnUseLastRbfCandidate").onclick = hydrateRbfBumpCard;
  if ($("btnPreviewRbfBump")) $("btnPreviewRbfBump").onclick = bumpFeeFromCard;
  $("btnCreateMultisig").onclick = createMultisigWallet;
  $("btnCreateMultisigSpend").onclick = createMultisigSpend;
  $("btnSignMultisigSpend").onclick = signMultisigSpend;
  $("btnExtractMultisigSpend").onclick = extractMultisigSpend;
  $("signedPsbtFile").onchange = async (ev) => {
    const file = ev.target.files && ev.target.files[0];
    if (!file) return;
    const text = (await file.text()).trim();
    $("signedPsbtOut").value = text;
    await importSignedPsbt(text);
  };
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
      markSendChecklist(risk, warnings);
      setWalletFlowStep("review");
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
    } catch (e) {
      msg.className = "err";
      msg.innerHTML = "Failed: " + esc(friendlyWalletErrorMessage(e, "Send review")) + '<span class="wallet-error-help">Check the recipient, amount, fee, and node connection before trying again.</span>';
      setWalletFlowStep("send-error");
    }
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
  if ($("btnBumpFee")) $("btnBumpFee").onclick = bumpLastFee;
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
      setWalletFlowStep("sent");
      pendingSend = null;
      $("sendReview").classList.add("hide");
      $("toAddr").value = ""; $("amount").value = ""; selectedOutpoints.clear(); renderUtxos(); setTimeout(refresh, 800);
    } catch (e) {
      msg.className = "err";
      msg.innerHTML = "Failed: " + esc(friendlyWalletErrorMessage(e, "Broadcast")) + '<span class="wallet-error-help">The transaction was not marked sent. Review the draft or try again after refreshing UTXOs.</span>';
      setWalletFlowStep("broadcast-error");
    }
  };

  // ---------- boot ----------
  ensureWalletTabShell();
  if ($("btnRegisterUsername")) $("btnRegisterUsername").onclick = registerUsername;
  if ($("btnLookupUsername")) $("btnLookupUsername").onclick = lookupUsername;
  if ($("btnCreateEscrow")) $("btnCreateEscrow").onclick = createEscrow;
  if ($("btnLoadEscrow")) $("btnLoadEscrow").onclick = loadEscrow;
  if ($("btnLoadMyEscrows")) $("btnLoadMyEscrows").onclick = loadMyEscrows;
  if ($("btnLoadContractTemplates")) $("btnLoadContractTemplates").onclick = loadContractTemplates;
  if ($("btnCreatePaymentLink")) $("btnCreatePaymentLink").onclick = createDevPaymentLink;
  if ($("btnCreateDevApiKey")) $("btnCreateDevApiKey").onclick = createDevApiKey;
  if ($("btnCopyDevApiKey")) $("btnCopyDevApiKey").onclick = () => navigator.clipboard.writeText($("devApiKeyField").value).catch(() => {});
  if ($("btnRegisterDevWebhook")) $("btnRegisterDevWebhook").onclick = registerDevWebhook;
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
