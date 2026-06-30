/* NetCoin Explorer — live, read-only. Talks only to a same-origin relay (/api/*)
   that proxies the node. No secrets, no writes. */
"use strict";
(function () {
  const API = (location.origin + "/api").replace(/\/$/, "");
  const COIN = 100000000;
  const CONTACTS_STORE = "ncw.contacts.v1";
  // NetCoin reward params (display only; mirror netcoin/params.py).
  const SCHEDULE_ACTIVATION = 4200, START_SUBSIDY = 50, REDUCTION_INTERVAL = 210000, REDUCTION_RATIO = 0.8;
  function rewardAtHeight(height) {
    let subsidy = START_SUBSIDY;
    const epochs = Math.floor(Math.max(0, height) / REDUCTION_INTERVAL);
    for (let i = 0; i < epochs; i++) subsidy *= REDUCTION_RATIO;
    return subsidy;
  }

  const $ = (s, r = document) => r.querySelector(s);
  const el = (h) => { const t = document.createElement("template"); t.innerHTML = h.trim(); return t.content.firstChild; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const trunc = (s, n = 20) => (s && s.length > n ? s.slice(0, n) + "…" : s || "");
  const fmtNet = (sats) => (sats / COIN).toLocaleString(undefined, { maximumFractionDigits: 8 });
  function ago(ts) {
    if (!ts) return "";
    const d = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (d < 60) return d + "s ago"; if (d < 3600) return Math.floor(d / 60) + "m ago";
    if (d < 86400) return Math.floor(d / 3600) + "h ago"; return Math.floor(d / 86400) + "d ago";
  }
  async function api(path) {
    const r = await fetch(API + path);
    const txt = await r.text(); let d; try { d = JSON.parse(txt); } catch { d = { error: txt }; }
    if (!r.ok || d.error) throw new Error(d.error || ("HTTP " + r.status));
    return d;
  }
  async function apiPost(path, body) {
    const r = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    const txt = await r.text(); let d; try { d = JSON.parse(txt); } catch { d = { error: txt }; }
    if (!r.ok || d.error) throw new Error(d.error || ("HTTP " + r.status));
    return d;
  }
  const view = $("#view");
  const setView = (node) => { view.replaceChildren(node); };

  const SITE_CONFIG = {
    explorer: { title: "Explorer", note: "Public chain data only: blocks, transactions, addresses, mempool, fees, peers, mining, and known labels.", route: "", nav: ["navHome", "navMempool", "navFees", "navPeers", "navStats", "navMining"] },
    pay: { title: "Pay", note: "Checkout, payment requests, receipts, tips, donations, and public profiles.", route: "#/payments", nav: ["navPayments", "navPos", "navNames"] },
    merchant: { title: "Merchant", note: "Merchant tools: invoices, POS, refunds, API keys, webhooks, and exports.", route: "#/merchant", nav: ["navMerchant", "navPos", "navPayments"] },
    faucet: { title: "Faucet", note: "Testnet coin claims and faucet health.", route: "#/faucet", nav: ["navFaucet", "navStats"] },
    status: { title: "Status", note: "Service and network health: node status, peers, faucet, mempool, and sync state.", route: "#/stats", nav: ["navStats", "navPeers", "navFaucet"] },
    community: { title: "Community", note: "Community tools: bounties, gifts, rewards, leaderboards, names, and profiles.", route: "#/community", nav: ["navCommunity", "navNames"] },
    markets: { title: "Markets", note: "Phase 7 testnet/demo area: polls, escrow, recurring agreements, contracts, and prediction-market demos.", route: "#/phase7", nav: ["navPhase7"] },
    docs: { title: "Docs", note: "User, merchant, developer, and operator documentation links.", route: "#/api", nav: ["navApi"] },
    api: { title: "API", note: "API reference and SDK entry point for developers.", route: "#/api", nav: ["navApi"] },
  };
  function configureSiteShell() {
    const site = document.body?.dataset?.site || "explorer";
    const cfg = SITE_CONFIG[site] || SITE_CONFIG.explorer;
    const h = $("#home");
    if (h) h.innerHTML = `Net<span>Coin</span> ${esc(cfg.title)}`;
    const note = $("#siteNote");
    if (note) note.textContent = cfg.note;
    const allowed = new Set(cfg.nav || []);
    document.querySelectorAll(".nav button").forEach((btn) => btn.classList.toggle("site-hidden", !allowed.has(btn.id)));
    const contacts = $("#contactsCard");
    if (contacts) contacts.classList.toggle("site-hidden", !["explorer", "pay", "community"].includes(site));
    if (!location.hash && cfg.route) location.hash = cfg.route;
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

  function contactNameFor(address) {
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    return contact ? contact.name : "";
  }

  function addressLink(address) {
    const label = contactNameFor(address);
    const suffix = label ? ` <span class="muted">(${esc(label)})</span>` : "";
    return `<a href="#/address/${encodeURIComponent(address)}">${esc(address)}</a>${suffix}`;
  }

  function setContactMsg(text, className = "muted") {
    const msg = $("#contactMsg");
    if (!msg) return;
    msg.className = className;
    msg.textContent = text;
  }

  function normalizeContactAddress(address) {
    const clean = String(address || "").trim();
    if (!clean) throw new Error("enter an address or public key first");
    return clean;
  }

  function renderContacts(selectedAddress = "") {
    const select = $("#contactSelect");
    if (!select) return;
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

  function fillContactForm(address, name = "") {
    const addrInput = $("#contactAddress");
    const nameInput = $("#contactName");
    if (!addrInput || !nameInput) return;
    addrInput.value = address || "";
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    nameInput.value = contact ? contact.name : name;
    const groupInput = $("#contactGroup"); if (groupInput) groupInput.value = contact ? (contact.group || "General") : "General";
    renderContacts(address || "");
  }

  function syncContactFormFromSelect() {
    const address = $("#contactSelect").value;
    if (!address) return;
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    fillContactForm(address, contact?.name || "");
    setContactMsg(contact ? `Selected ${contact.name}.` : "Selected saved address.");
  }

  function syncContactNameFromAddress() {
    const address = $("#contactAddress").value.trim();
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    if (contact) {
      $("#contactName").value = contact.name;
    }
    renderContacts(address);
  }

  function saveContactFromFields() {
    try {
      const address = normalizeContactAddress($("#contactAddress").value);
      const name = $("#contactName").value.trim();
      if (!name) throw new Error("enter a contact name first");

      const contacts = loadContacts();
      const existingIndex = contacts.findIndex((c) => sameAddress(c.address, address));
      const group = ($("#contactGroup")?.value || "General").trim() || "General";
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

  function viewSelectedContact() {
    const selectAddress = $("#contactSelect").value;
    const typedAddress = $("#contactAddress").value.trim();
    const address = selectAddress || typedAddress;
    if (!address) {
      setContactMsg("Choose or enter a contact first.", "err");
      return;
    }
    const contact = loadContacts().find((c) => sameAddress(c.address, address));
    if (contact) fillContactForm(contact.address, contact.name);
    setContactMsg(contact ? `Opening ${contact.name}.` : "Opening address.", "ok");
    location.hash = "#/address/" + encodeURIComponent(address);
  }

  function deleteSelectedContact() {
    const address = $("#contactSelect").value;
    if (!address) {
      setContactMsg("Choose a saved contact to delete.", "err");
      return;
    }
    const contacts = loadContacts();
    const contact = contacts.find((c) => sameAddress(c.address, address));
    const label = contact ? contact.name : shortAddress(address);
    if (!confirm(`Delete ${label} from saved contacts?`)) return;
    saveContacts(contacts.filter((c) => !sameAddress(c.address, address)));
    fillContactForm("", "");
    setContactMsg(`Deleted ${label}.`, "ok");
  }

  // ---------- emission / supply panel ----------
  function fallbackSupply(height) {
    return {
      total_minted: (height * START_SUBSIDY).toFixed(8),
      next_subsidy: rewardAtHeight(height + 1).toFixed(8),
    };
  }
  function displayNet(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 8 }) : esc(value ?? "0");
  }
  function emissionCard(height, supply) {
    const active = height >= SCHEDULE_ACTIVATION;
    const nextEvent = active ? (Math.floor(height / REDUCTION_INTERVAL) + 1) * REDUCTION_INTERVAL : SCHEDULE_ACTIVATION;
    const blocksLeft = Math.max(0, nextEvent - height);
    const pct = active
      ? Math.min(100, ((height % REDUCTION_INTERVAL) / REDUCTION_INTERVAL) * 100)
      : Math.min(100, (height / SCHEDULE_ACTIVATION) * 100);
    const status = active
      ? `Reward schedule <b class="acc">active</b> — starts at ${START_SUBSIDY} NET and decreases 20% every ${REDUCTION_INTERVAL.toLocaleString()} blocks. Next reduction at height ${nextEvent.toLocaleString()} (<b>${blocksLeft.toLocaleString()}</b> blocks).`
      : `Upgrade pending — deterministic 20% reward schedule activates at height ${SCHEDULE_ACTIVATION.toLocaleString()} (<b>${blocksLeft.toLocaleString()}</b> blocks to go).`;
    return el(`<div class="card">
      <h2>Emission</h2>
      <div class="muted" style="margin-bottom:10px">${status}</div>
      <div class="bar"><i style="width:${pct.toFixed(1)}%"></i></div>
      <div class="muted" style="margin-top:6px">${displayNet(supply.total_minted)} NET minted · next subsidy ${displayNet(supply.next_subsidy)} NET/block</div>
    </div>`);
  }

  // ---------- home ----------
  async function home() {
    let info, latest, supply, latestTxs;
    try {
      info = (await api("/info")).node;
      latest = await api("/latest?n=15");
      try { latestTxs = await api("/latest-txs?n=12"); } catch { latestTxs = { confirmed: [], mempool: [] }; }
      try { supply = await api("/supply"); } catch { supply = fallbackSupply(info.height); }
    }
    catch (e) { setView(el(`<div class="card err">Cannot reach the node: ${esc(e.message)}</div>`)); return; }

    const stats = el(`<div class="stats">
      <div class="stat"><div class="k">Height</div><div class="v">${info.height.toLocaleString()}</div></div>
      <div class="stat"><div class="k">Mempool</div><div class="v"><a href="#/mempool">${info.mempool_transactions ?? 0}</a></div></div>
      <div class="stat"><div class="k">Difficulty (bits)</div><div class="v mono" style="font-size:14px">0x${(info.bits>>>0).toString(16)}</div></div>
      <div class="stat"><div class="k">Next Subsidy</div><div class="v">${displayNet(supply.next_subsidy)} <span class="muted" style="font-size:13px">NET</span></div></div>
    </div>`);

    const rows = latest.blocks.map((b) => `<tr>
      <td>${b.height}</td>
      <td class="mono"><a href="#/block/${b.hash}">${trunc(b.hash, 18)}</a></td>
      <td class="right">${b.transactions}</td>
      <td class="right muted">${b.weight}</td>
      <td class="right muted">${ago(b.timestamp)}</td></tr>`).join("");
    const blocks = el(`<div class="card"><h2>Latest blocks</h2>
      <table><thead><tr><th>Height</th><th>Hash</th><th class="right">Txs</th><th class="right">Weight</th><th class="right">Age</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`);

    const txItems = [...(latestTxs.mempool || []), ...(latestTxs.confirmed || [])].slice(0, 12);
    const txRows = txItems.map((t) => `<tr><td class="mono trunc"><a href="#/tx/${esc(t.txid)}">${esc(t.txid)}</a></td><td>${t.confirmed ? "confirmed" : "mempool"}</td><td class="right">${fmtNet(t.total_output_sats || 0)} NET</td><td class="right muted">${t.block_height ?? "—"}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No transactions yet.</td></tr>`;
    const txFeed = el(`<div class="card"><h2>Newest transactions</h2><table><thead><tr><th>Txid</th><th>Status</th><th class="right">Output total</th><th class="right">Height</th></tr></thead><tbody>${txRows}</tbody></table></div>`);
    const frag = document.createDocumentFragment();
    frag.append(stats, emissionCard(info.height, supply), blocks, txFeed);
    setView(frag);
  }

  // ---------- block ----------
  async function block(hash) {
    setView(el(`<div class="card muted">Loading block…</div>`));
    let b; try { b = await api("/block/" + hash); } catch (e) { return setView(el(`<div class="card err">Block not found: ${esc(e.message)}</div>`)); }
    const h = b.header || {};
    const coinbaseOut = b.coinbase_value_sats ?? (b.transactions?.[0]?.outputs || []).reduce((s, o) => s + (o.amount || 0), 0);
    const subsidy = b.subsidy_sats ?? 0;
    const fees = b.fees_sats ?? Math.max(0, coinbaseOut - subsidy);
    const txRows = (b.transactions || []).map((t, i) => {
      const outs = (t.outputs || []).map((o) => `<div class="mono trunc">${addressLink(o.address)} · <span class="acc">${fmtNet(o.amount)} NET</span></div>`).join("");
      return `<tr><td>${i === 0 ? '<span class="acc">coinbase</span>' : "tx"}</td><td>${outs}</td></tr>`;
    }).join("");
    setView(el(`<div>
      <div class="back" id="bk">← back</div>
      <div class="card"><h2>Block ${h.height ?? ""}</h2>
        <div class="kv">
          <div class="k">Hash</div><div class="v mono">${esc(b.hash)}</div>
          <div class="k">Previous</div><div class="v mono"><a href="#/block/${esc(h.previous_hash)}">${esc(h.previous_hash)}</a></div>
          <div class="k">Timestamp</div><div class="v">${h.timestamp ? new Date(h.timestamp*1000).toUTCString() : ""} <span class="muted">(${ago(h.timestamp)})</span></div>
          <div class="k">Merkle root</div><div class="v mono">${esc(h.merkle_root)}</div>
          <div class="k">Bits / Nonce</div><div class="v mono">0x${(h.bits>>>0).toString(16)} / ${h.nonce}</div>
          <div class="k">Weight</div><div class="v">${b.weight}</div>
          <div class="k">Coinbase value</div><div class="v acc">${fmtNet(coinbaseOut)} NET</div>
          <div class="k">Subsidy</div><div class="v">${fmtNet(subsidy)} NET</div>
          <div class="k">Fees</div><div class="v">${fmtNet(fees)} NET</div>
        </div></div>
      <div class="card"><h2>Transactions (${(b.transactions||[]).length})</h2>
        <table><tbody>${txRows}</tbody></table><h2>Team wallet proposal</h2><input id="teamId" placeholder="team wallet id" /><input id="teamName" placeholder="team name" /><input id="teamRequired" placeholder="required approvals" value="2" /><button id="btnTeam" type="button">Create team wallet</button><input id="teamTo" class="mono" placeholder="proposal recipient address" /><input id="teamAmount" placeholder="proposal amount NET" /><button id="btnTeamProposal" class="secondary" type="button">Create proposal</button><pre id="teamOut"></pre></div></div>`));
    $("#bk").onclick = () => history.back();
  }

  // ---------- address ----------
  async function address(addr) {
    setView(el(`<div class="card muted">Loading address…</div>`));
    let a; try { a = await api("/address/" + encodeURIComponent(addr)); } catch (e) { return setView(el(`<div class="card err">${esc(e.message)}</div>`)); }
    const bal = a.balance || {};
    const txids = (a.transaction_ids || []).slice(-25).reverse();
    const txRows = txids.map((t) => `<tr><td class="mono trunc"><a href="#/tx/${t}">${t}</a></td></tr>`).join("") || `<tr><td class="muted">No transactions.</td></tr>`;
    setView(el(`<div>
      <div class="back" id="bk">← back</div>
      <div class="card"><h2>Address${contactNameFor(a.address) ? ` · ${esc(contactNameFor(a.address))}` : ""}</h2>
        <div class="mono" style="word-break:break-all;margin-bottom:12px">${esc(a.address)}</div>
        <div class="stats">
          <div class="stat"><div class="k">Total</div><div class="v acc">${fmtNet(bal.total||0)} NET</div></div>
          <div class="stat"><div class="k">Spendable</div><div class="v">${fmtNet(bal.spendable||0)} NET</div></div>
          <div class="stat"><div class="k">Immature</div><div class="v warn">${fmtNet(bal.immature||0)} NET</div></div>
          <div class="stat"><div class="k">Txs</div><div class="v">${a.transaction_count ?? txids.length}</div></div>
        </div></div>
      <div class="card"><h2>Recent transactions</h2><table><tbody>${txRows}</tbody></table></div></div>`));
    fillContactForm(a.address);
    setContactMsg("Viewing address. Add a name above and save it as a contact.");
    $("#bk").onclick = () => history.back();
  }

  // ---------- tx ----------
  async function tx(txid) {
    setView(el(`<div class="card muted">Loading transaction…</div>`));
    let t; try { t = await api("/tx/" + txid); } catch (e) { return setView(el(`<div class="card err">Transaction not found: ${esc(e.message)}</div>`)); }
    const d = t.transaction || t.tx || t;
    const outs = (d.outputs || []).map((o) => `<tr><td class="mono trunc">${addressLink(o.address || "")}</td><td class="right acc">${fmtNet(o.amount || 0)} NET</td></tr>`).join("");
    const ins = (d.inputs || []).map((i) => `<tr><td class="mono trunc">${i.coinbase ? '<span class="acc">coinbase</span>' : esc((i.txid||"")+":"+i.vout)}</td></tr>`).join("");
    const status = t.confirmed ? "confirmed" : "mempool / unconfirmed";
    setView(el(`<div>
      <div class="back" id="bk">← back</div>
      <div class="card"><h2>Transaction</h2>
        <div class="mono" style="word-break:break-all">${esc(txid)}</div>
        <div class="kv" style="margin-top:10px">
          <div class="k">Status</div><div class="v">${esc(status)}</div>
          <div class="k">wtxid</div><div class="v mono">${esc(t.wtxid || d.wtxid || "")}</div>
          <div class="k">Block</div><div class="v">${t.block_hash ? `<a href="#/block/${esc(t.block_hash)}">${trunc(t.block_hash,18)}</a> · height ${t.block_height ?? t.height ?? ""}` : "—"}</div>
          <div class="k">Inputs / outputs</div><div class="v">${(d.inputs||[]).length} / ${(d.outputs||[]).length}</div>
        </div></div>
      <div class="card"><h2>Inputs</h2><table><tbody>${ins||'<tr><td class="muted">—</td></tr>'}</tbody></table></div>
      <div class="card"><h2>Outputs</h2><table><tbody>${outs}</tbody></table></div>
      <div class="card"><h2>Raw JSON</h2><pre>${esc(JSON.stringify(t, null, 2))}</pre></div></div>`));
    $("#bk").onclick = () => history.back();
  }


  // ---------- mempool / fees / peers / API docs ----------
  async function mempool() {
    setView(el(`<div class="card muted">Loading mempool…</div>`));
    try {
      const d = await api("/mempool");
      const entries = d.entries || d.mempool?.entries || [];
      const rows = entries.map((e) => `<tr><td class="mono trunc"><a href="#/tx/${esc(e.txid)}">${esc(e.txid)}</a></td><td class="right">${e.vsize ?? ""}</td><td class="right">${e.fee ?? ""}</td><td class="right">${e.fee_rate_per_kvb ?? ""}</td><td>${e.rbf ? "yes" : "no"}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">No unconfirmed transactions.</td></tr>`;
      const packages = d.packages || [];
      const packageRows = packages.map((p) => `<tr><td>${p.count}</td><td class="mono trunc">${(p.txids || []).map((t) => `<a href="#/tx/${esc(t)}">${trunc(t, 12)}</a>`).join(", ")}</td><td class="right">${p.vsize}</td><td class="right">${p.fee}</td><td class="right">${p.fee_rate_per_kvb}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">No package groups.</td></tr>`;
      setView(el(`<div><div class="card"><h2>Mempool</h2><div class="stats"><div class="stat"><div class="k">Transactions</div><div class="v">${d.size ?? entries.length}</div></div><div class="stat"><div class="k">Virtual bytes</div><div class="v">${d.bytes ?? 0}</div></div><div class="stat"><div class="k">Packages</div><div class="v">${packages.length}</div></div><div class="stat"><div class="k">Min relay fee /kvB</div><div class="v">${d.min_relay_fee_per_kvb ?? "—"}</div></div></div></div><div class="card"><h2>Unconfirmed transactions</h2><table><thead><tr><th>txid</th><th class="right">vsize</th><th class="right">fee sats</th><th class="right">fee/kvB</th><th>RBF</th></tr></thead><tbody>${rows}</tbody></table></div><div class="card"><h2>CPFP / package groups</h2><table><thead><tr><th>Count</th><th>Transactions</th><th class="right">vsize</th><th class="right">fee sats</th><th class="right">fee/kvB</th></tr></thead><tbody>${packageRows}</tbody></table></div></div>`));
    } catch (e) { setView(el(`<div class="card err">Could not load mempool: ${esc(e.message)}</div>`)); }
  }

  async function fees() {
    setView(el(`<div class="card muted">Loading fee estimates…</div>`));
    try {
      const d = await api("/fee-estimates");
      const rows = Object.entries(d.presets || {}).map(([name, info]) => `<tr><td>${esc(name)}</td><td class="right">${info.target_blocks}</td><td class="right">${info.fee_rate_per_kvb}</td><td class="right acc">${fmtNet(info.estimated_fee_sats || 0)} NET</td></tr>`).join("");
      setView(el(`<div class="card"><h2>Fee estimates</h2><p class="muted">Local policy estimate based on current mempool. Estimated fee assumes a typical 200 vbyte transaction.</p><table><thead><tr><th>Preset</th><th class="right">Target blocks</th><th class="right">sats/kvB</th><th class="right">Typical fee</th></tr></thead><tbody>${rows}</tbody></table></div>`));
    } catch (e) { setView(el(`<div class="card err">Could not load fees: ${esc(e.message)}</div>`)); }
  }

  async function peers() {
    setView(el(`<div class="card muted">Loading peers…</div>`));
    try {
      const d = await api("/peers");
      const rows = (d.peers || []).map((peer) => `<tr><td class="mono">${esc(peer)}</td><td>${esc(d.scores?.[peer] ?? "")}</td></tr>`).join("") || `<tr><td colspan="2" class="muted">No peer list exposed by this explorer.</td></tr>`;
      setView(el(`<div class="card"><h2>Seed / peer status</h2><table><thead><tr><th>Peer</th><th>Score</th></tr></thead><tbody>${rows}</tbody></table><p class="muted">Banned peers: ${(d.banned || []).map(esc).join(", ") || "none"}</p></div>`));
    } catch (e) { setView(el(`<div class="card err">Could not load peers: ${esc(e.message)}</div>`)); }
  }

  async function networkStats() {
    setView(el(`<div class="card muted">Loading network stats…</div>`));
    try {
      const latest = await api("/latest?n=1");
      const start = Math.max(0, (latest.height || 0) - 99);
      const d = await api(`/headers?start=${start}&limit=100`);
      const headers = d.headers || [];
      const bits = headers.map((h) => Number(h.bits || 0));
      const times = headers.map((h) => Number(h.timestamp || 0)).filter(Boolean);
      const minBits = Math.min(...bits), maxBits = Math.max(...bits);
      const bars = headers.slice(-40).map((h) => {
        const b = Number(h.bits || 0);
        const pct = maxBits === minBits ? 100 : 8 + ((b - minBits) / Math.max(1, maxBits - minBits)) * 92;
        return `<div class="mini-bar"><span>#${h.height}</span><span><i style="width:${pct.toFixed(1)}%"></i></span><span class="mono">0x${(b>>>0).toString(16)}</span></div>`;
      }).join("");
      const span = times.length > 1 ? times[times.length - 1] - times[0] : 0;
      const avg = times.length > 1 ? span / (times.length - 1) : 0;
      setView(el(`<div><div class="card"><h2>Network stats</h2><div class="stats"><div class="stat"><div class="k">Height</div><div class="v">${latest.height ?? "—"}</div></div><div class="stat"><div class="k">Sampled headers</div><div class="v">${headers.length}</div></div><div class="stat"><div class="k">Avg block interval</div><div class="v">${avg ? Math.round(avg) + "s" : "—"}</div></div><div class="stat"><div class="k">Tip bits</div><div class="v mono">0x${((bits[bits.length-1] || 0)>>>0).toString(16)}</div></div></div></div><div class="card"><h2>Recent difficulty bits</h2><div class="mini-bars">${bars || '<span class="muted">No headers.</span>'}</div><p class="muted">This shows compact difficulty bits over recent blocks. A full hash-rate estimate should be treated as an approximation on small/test networks.</p></div></div>`));
    } catch (e) { setView(el(`<div class="card err">Could not load stats: ${esc(e.message)}</div>`)); }
  }


  async function faucetStatus() {
    setView(el(`<div class="card muted">Loading faucet status…</div>`));
    try {
      let d;
      try {
        const r = await fetch("/faucet/status");
        const txt = await r.text();
        d = JSON.parse(txt);
        if (!r.ok || d.error) throw new Error(d.error || "HTTP " + r.status);
      } catch {
        d = await api("/faucet/status");
      }
      const hw = d.hot_wallet || {};
      const stateClass = hw.state === "ok" ? "ok" : (hw.state === "needs_refill" ? "warn" : "muted");
      setView(el(`<div><div class="card"><h2>Faucet status</h2><div class="stats"><div class="stat"><div class="k">Queue mode</div><div class="v">${esc(d.queue_mode || "—")}</div></div><div class="stat"><div class="k">Queued</div><div class="v">${d.queued ?? "—"}</div></div><div class="stat"><div class="k">CAPTCHA</div><div class="v">${d.captcha?.enabled ? esc(d.captcha.provider || "enabled") : "off"}</div></div><div class="stat"><div class="k">Hot wallet</div><div class="v ${stateClass}">${esc(hw.state || "unknown")}</div></div></div><div class="kv"><div class="k">Spendable sats</div><div class="v">${hw.spendable_sats ?? "unknown"}</div><div class="k">Refill address</div><div class="v mono">${esc(hw.refill_address || "—")}</div></div></div><div class="card"><h2>Notes</h2><p class="muted">This page reads the faucet public /status endpoint when it is mounted under the explorer origin. If your faucet runs on another domain, proxy /faucet/status through the same origin to keep the explorer CSP strict.</p></div></div>`));
    } catch (e) {
      setView(el(`<div class="card err">Could not load faucet status: ${esc(e.message)}<p class="muted">Run the faucet behind the same origin at /faucet/status or add an explorer proxy endpoint.</p></div>`));
    }
  }

  async function paymentsPage() {
    setView(el(`<div class="card muted">Loading payment tools…</div>`));
    let invoices = [];
    try { invoices = (await api("/invoices?limit=20")).invoices || []; } catch { invoices = []; }
    const rows = invoices.map((i) => `<tr><td class="mono"><a href="#/checkout/${esc(i.invoice_id)}">${esc(i.invoice_id)}</a></td><td>${esc(i.status)}</td><td class="right acc">${esc(i.amount)} NET</td><td class="mono trunc">${esc(i.recipient_address)}</td><td class="mono trunc">${i.receipt_txid ? `<a href="#/receipt/${esc(i.receipt_txid)}">${esc(i.receipt_txid)}</a>` : "—"}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">No invoices yet.</td></tr>`;
    setView(el(`<div>
      <div class="card"><h2>Create invoice / checkout</h2>
        <p class="muted">Create a payment request, checkout link, and status tracker. This is app-layer state; it does not change consensus.</p>
        <input id="payAddress" class="mono" placeholder="Recipient NetCoin address" autocomplete="off" />
        <div class="row"><input id="payAmount" placeholder="Amount NET" inputmode="decimal" /><input id="payOrder" placeholder="Order ID / label" /></div>
        <input id="payMemo" placeholder="Memo" />
        <button id="btnCreateInvoice" type="button">Create invoice</button>
        <p id="payMsg" class="muted"></p>
      </div>
      <div class="card"><h2>Recent invoices</h2><table><thead><tr><th>ID</th><th>Status</th><th class="right">Amount</th><th>Recipient</th><th>Receipt</th></tr></thead><tbody>${rows}</tbody></table></div>
    </div>`));
    $("#btnCreateInvoice").onclick = async () => {
      const msg = $("#payMsg");
      try {
        const inv = await apiPost("/invoices", { address: $("#payAddress").value.trim(), amount: $("#payAmount").value.trim(), memo: $("#payMemo").value.trim(), order_id: $("#payOrder").value.trim(), label: $("#payOrder").value.trim() });
        msg.className = "ok"; msg.innerHTML = `Created <a href="#/checkout/${esc(inv.invoice_id)}">${esc(inv.invoice_id)}</a> · public page <a href="/pay/${esc(inv.invoice_id)}" target="_blank" rel="noreferrer">/pay/${esc(inv.invoice_id)}</a>. URI: <span class="mono">${esc(inv.payment_uri)}</span>`;
      } catch (e) { msg.className = "err"; msg.textContent = e.message; }
    };
  }

  async function checkoutPage(id) {
    setView(el(`<div class="card muted">Loading checkout…</div>`));
    try {
      const i = await api("/checkout/" + encodeURIComponent(id));
      const inv = i.checkout || i;
      setView(el(`<div><div class="back" id="bk">← back</div><div class="card"><h2>Checkout ${esc(inv.invoice_id)}</h2><div class="stats"><div class="stat"><div class="k">Status</div><div class="v ${inv.status === "confirmed" ? "ok" : "warn"}">${esc(inv.status)}</div></div><div class="stat"><div class="k">Amount</div><div class="v acc">${esc(inv.amount)} NET</div></div><div class="stat"><div class="k">Paid</div><div class="v">${esc(inv.paid_total || "0")} NET</div></div></div><div class="kv"><div class="k">Address</div><div class="v mono">${esc(inv.recipient_address)}</div><div class="k">Payment URI</div><div class="v mono">${esc(inv.payment_uri)}</div><div class="k">Public checkout</div><div class="v mono"><a href="/pay/${esc(inv.invoice_id)}" target="_blank" rel="noreferrer">/pay/${esc(inv.invoice_id)}</a></div><div class="k">Memo</div><div class="v">${esc(inv.memo || "")}</div><div class="k">Order</div><div class="v">${esc(inv.order_id || "")}</div><div class="k">Receipt</div><div class="v mono">${inv.receipt_txid ? `<a href="#/receipt/${esc(inv.receipt_txid)}">${esc(inv.receipt_txid)}</a> · <a href="/receipt/${esc(inv.receipt_txid)}.pdf" target="_blank" rel="noreferrer">PDF</a>` : "—"}</div></div></div><div class="card"><h2>Matching transactions</h2><pre>${esc(JSON.stringify(inv.matching_transactions || [], null, 2))}</pre></div></div>`));
      $("#bk").onclick = () => history.back();
    } catch (e) { setView(el(`<div class="card err">Could not load checkout: ${esc(e.message)}</div>`)); }
  }

  async function receiptPage(txid) {
    setView(el(`<div class="card muted">Loading receipt…</div>`));
    try {
      const r = await api("/receipt/" + encodeURIComponent(txid));
      setView(el(`<div><div class="back" id="bk">← back</div><div class="card"><h2>Transaction receipt</h2><div class="kv"><div class="k">Txid</div><div class="v mono">${esc(r.txid)}</div><div class="k">Status</div><div class="v">${r.confirmed ? "confirmed" : "unconfirmed"}</div><div class="k">Confirmations</div><div class="v">${r.confirmations}</div><div class="k">Block</div><div class="v mono">${r.block_hash ? `<a href="#/block/${esc(r.block_hash)}">${esc(r.block_hash)}</a>` : "—"}</div><div class="k">Total output</div><div class="v acc">${esc(r.total_output)} NET</div></div></div><div class="card"><h2>Outputs by address</h2><pre>${esc(JSON.stringify(r.outputs_to_address || {}, null, 2))}</pre></div><div class="card"><h2>Linked invoices</h2><pre>${esc(JSON.stringify(r.linked_invoices || [], null, 2))}</pre></div></div>`));
      $("#bk").onclick = () => history.back();
    } catch (e) { setView(el(`<div class="card err">Could not load receipt: ${esc(e.message)}</div>`)); }
  }

  async function namesPage() {
    let names = [];
    try { names = (await api("/usernames")).usernames || []; } catch { names = []; }
    const rows = names.map((n) => `<tr><td><a href="#/u/${esc(n.username)}">${esc(n.username)}</a></td><td>${esc(n.display_name || "")}</td><td>${n.verified ? "verified" : ""}</td><td class="mono trunc">${addressLink(n.address)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No usernames registered locally.</td></tr>`;
    setView(el(`<div><div class="card"><h2>NetCoin usernames and profiles</h2><p class="muted">Centralized local registry for easier sending. Use it now; migrate to on-chain names later.</p><input id="nameUser" placeholder="username" /><input id="nameDisplay" placeholder="display name" /><input id="nameAddress" class="mono" placeholder="NetCoin address" /><textarea id="nameBio" placeholder="public profile bio"></textarea><button id="btnSaveName" type="button">Save username/profile</button><p id="nameMsg" class="muted"></p></div><div class="card"><h2>Profiles</h2><table><thead><tr><th>Name</th><th>Display</th><th>Status</th><th>Address</th></tr></thead><tbody>${rows}</tbody></table></div></div>`));
    $("#btnSaveName").onclick = async () => { const msg = $("#nameMsg"); try { const r = await apiPost("/usernames", { username: $("#nameUser").value, display_name: $("#nameDisplay").value, address: $("#nameAddress").value, bio: $("#nameBio").value }); msg.className = "ok"; msg.textContent = `Saved ${r.username}.`; } catch(e) { msg.className = "err"; msg.textContent = e.message; } };
  }

  async function profilePage(name) {
    try { const p = await api("/profiles/" + encodeURIComponent(name)); setView(el(`<div><div class="back" id="bk">← back</div><div class="card"><h2>${esc(p.display_name || p.username)} ${p.verified ? '<span class="ok">✓ verified</span>' : ''}</h2><p>${esc(p.bio || "")}</p><div class="kv"><div class="k">Username</div><div class="v">${esc(p.username)}</div><div class="k">Address</div><div class="v mono">${addressLink(p.address)}</div><div class="k">Payment page</div><div class="v mono">#/address/${esc(p.address)}</div></div></div></div>`)); $("#bk").onclick = () => history.back(); } catch(e) { setView(el(`<div class="card err">Profile not found: ${esc(e.message)}</div>`)); }
  }

  async function posPage() {
    setView(el(`<div><div class="card"><h2>Point-of-sale mode</h2><p class="muted">Tablet-friendly checkout creator. Enter an amount, create a checkout, then show the customer the public payment page.</p><input id="posAddress" class="mono" placeholder="merchant receive address" /><input id="posAmount" placeholder="amount NET" inputmode="decimal" /><input id="posMemo" placeholder="sale memo / item" /><button id="btnPosCreate" type="button">Create checkout</button><p id="posMsg" class="muted"></p></div><div class="card"><h2>Customer screen</h2><iframe id="posFrame" title="checkout" style="width:100%;height:480px;border:1px solid #ddd;border-radius:12px"></iframe></div></div>`));
    $("#btnPosCreate").onclick = async () => { const msg=$("#posMsg"); try { const inv=await apiPost("/invoices", { address: $("#posAddress").value, amount: $("#posAmount").value, memo: $("#posMemo").value, label: "POS" }); msg.className="ok"; msg.innerHTML=`Checkout ready: <a href="/pay/${esc(inv.invoice_id)}" target="_blank" rel="noreferrer">/pay/${esc(inv.invoice_id)}</a>`; $("#posFrame").src = "/pay/" + encodeURIComponent(inv.invoice_id); } catch(e){ msg.className="err"; msg.textContent=e.message; } };
  }

  async function merchantPage() {
    setView(el(`<div><div class="card"><h2>Merchant tools</h2><p class="muted">Create API keys, webhook subscriptions, refunds, and sales exports.</p><input id="merchId" placeholder="merchant id" value="default" /><input id="merchantApiKey" class="mono" placeholder="API key for protected writes, optional" /><div class="row"><button id="btnApiKey" type="button">Create API key</button><button id="btnEnforceKey" class="secondary" type="button">Require API key</button></div><p id="keyMsg" class="muted"></p><input id="hookUrl" placeholder="https://example.com/netcoin-webhook" /><div class="row"><button id="btnWebhook" type="button">Register webhook</button><button id="btnDeliverHooks" class="secondary" type="button">Deliver queued webhooks</button></div><p id="hookMsg" class="muted"></p><h2>Refund flow</h2><input id="refAddr" class="mono" placeholder="refund address" /><input id="refAmount" placeholder="amount NET" /><input id="refReason" placeholder="reason" /><div class="row"><button id="btnRefund" type="button">Record refund</button><button id="btnRefundPlan" class="secondary" type="button">Create refund payout plan</button></div><p id="refMsg" class="muted"></p><p><a href="/api/merchant/export.csv" target="_blank" rel="noreferrer">Download sales CSV</a></p></div></div>`));
    $("#btnApiKey").onclick = async () => { const msg=$("#keyMsg"); try { const r=await apiPost("/merchant/api-keys", { merchant_id: $("#merchId").value }); msg.className="ok"; msg.innerHTML=`API key: <span class="mono">${esc(r.api_key)}</span>`; $("#merchantApiKey").value = r.api_key; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnEnforceKey").onclick = async () => { const msg=$("#keyMsg"); try { const r=await apiPost("/merchant/api-keys/enforce", { merchant_id: $("#merchId").value, required: true }); msg.className="ok"; msg.textContent=`API-key enforcement enabled for ${r.merchant_id}.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnWebhook").onclick = async () => { const msg=$("#hookMsg"); try { const r=await apiPost("/merchant/webhooks", { merchant_id: $("#merchId").value, url: $("#hookUrl").value, api_key: $("#merchantApiKey").value }); msg.className="ok"; msg.innerHTML=`Webhook saved. Secret: <span class="mono">${esc(r.secret)}</span>`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnDeliverHooks").onclick = async () => { const msg=$("#hookMsg"); try { const r=await apiPost("/merchant/webhook-events/deliver", { max_events: 20 }); msg.className="ok"; msg.textContent=`Delivered ${r.delivered}, failed ${r.failed}.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnRefund").onclick = async () => { const msg=$("#refMsg"); try { const r=await apiPost("/merchant/refunds", { to_address: $("#refAddr").value, amount: $("#refAmount").value, reason: $("#refReason").value, api_key: $("#merchantApiKey").value }); msg.className="ok"; msg.textContent=`Refund record ${r.refund_id} saved.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnRefundPlan").onclick = async () => { const msg=$("#refMsg"); try { const r=await apiPost("/merchant/refunds/plan", { to_address: $("#refAddr").value, amount: $("#refAmount").value, reason: $("#refReason").value, api_key: $("#merchantApiKey").value }); msg.className="ok"; msg.textContent=`Refund payout plan ${r.payout_plan.payout_id} ready for wallet signing.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
  }

  async function communityPage() {
    let boards = {}; let bounties = [];
    try { boards = await api("/community/leaderboards"); } catch { boards = {}; }
    try { bounties = (await api("/community/bounties")).bounties || []; } catch { bounties = []; }
    const top = (boards.top_miners || []).slice(0,5).map((x) => `<li class="mono">${esc(x.id || x.address)} · ${esc(x.amount || x.reward || "")} NET</li>`).join("") || `<li class="muted">No data yet.</li>`;
    const bountyRows = bounties.map((b) => `<tr><td>${esc(b.title)}</td><td>${esc(b.status)}</td><td class="right acc">${esc(b.reward)} NET</td></tr>`).join("") || `<tr><td colspan="3" class="muted">No bounties yet.</td></tr>`;
    setView(el(`<div><div class="card"><h2>Gift links</h2><input id="giftAmount" placeholder="amount NET" /><input id="giftMemo" placeholder="memo" /><button id="btnGift" type="button">Create gift link</button><p id="giftMsg" class="muted"></p></div><div class="card"><h2>Airdrop dry run</h2><textarea id="airdropAddresses" placeholder="one address per line or comma-separated"></textarea><input id="airdropAmount" placeholder="amount per address NET" /><button id="btnAirdrop" type="button">Check airdrop</button><button id="btnAirdropPlan" class="secondary" type="button">Create payout plan</button><pre id="airdropOut"></pre></div><div class="card"><h2>Creator tip button</h2><input id="tipAddress" class="mono" placeholder="creator address" /><input id="tipLabel" placeholder="button label" value="Tip with NetCoin" /><button id="btnTipButton" type="button">Generate button</button><pre id="tipButtonOut"></pre></div><div class="card"><h2>Community reward</h2><input id="rewardAddress" class="mono" placeholder="recipient address" /><input id="rewardAmount" placeholder="amount NET" /><input id="rewardReason" placeholder="reason" /><button id="btnReward" type="button">Create reward payout plan</button><p id="rewardMsg" class="muted"></p></div><div class="card"><h2>Bounty board</h2><input id="bountyTitle" placeholder="bounty title" /><input id="bountyReward" placeholder="reward NET" /><textarea id="bountyDesc" placeholder="description"></textarea><button id="btnBounty" type="button">Create bounty</button><table><thead><tr><th>Title</th><th>Status</th><th class="right">Reward</th></tr></thead><tbody>${bountyRows}</tbody></table></div><div class="card"><h2>Leaderboards</h2><ul>${top}</ul></div></div>`));
    $("#btnGift").onclick = async () => { const msg=$("#giftMsg"); try { const r=await apiPost("/community/gifts", { amount: $("#giftAmount").value, memo: $("#giftMemo").value }); msg.className="ok"; msg.innerHTML=`Gift code: <span class="mono">${esc(r.claim_code)}</span>`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnAirdrop").onclick = async () => { try { const r=await apiPost("/community/airdrops", { addresses: $("#airdropAddresses").value, amount: $("#airdropAmount").value, dry_run: true }); $("#airdropOut").textContent=JSON.stringify(r,null,2); } catch(e){ $("#airdropOut").textContent=e.message; } };
    $("#btnAirdropPlan").onclick = async () => { try { const r=await apiPost("/community/airdrops", { addresses: $("#airdropAddresses").value, amount: $("#airdropAmount").value, dry_run: false }); $("#airdropOut").textContent=JSON.stringify(r.payout_plan || r,null,2); } catch(e){ $("#airdropOut").textContent=e.message; } };
    $("#btnTipButton").onclick = async () => { try { const r=await apiPost("/community/tip-buttons", { address: $("#tipAddress").value, label: $("#tipLabel").value }); $("#tipButtonOut").textContent=r.html; } catch(e){ $("#tipButtonOut").textContent=e.message; } };
    $("#btnReward").onclick = async () => { const msg=$("#rewardMsg"); try { const r=await apiPost("/community/rewards", { address: $("#rewardAddress").value, amount: $("#rewardAmount").value, reason: $("#rewardReason").value }); msg.className="ok"; msg.textContent=`Reward payout plan ${r.payout_plan.payout_id} ready.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnBounty").onclick = async () => { try { await apiPost("/community/bounties", { title: $("#bountyTitle").value, reward: $("#bountyReward").value, description: $("#bountyDesc").value }); communityPage(); } catch(e){ alert(e.message); } };
  }

  async function walletToolsPage() {
    setView(el(`<div><div class="card"><h2>Wallet reports, alerts, and limits</h2><input id="stmtAddr" class="mono" placeholder="address" /><input id="stmtMonth" placeholder="YYYY-MM optional" /><button id="btnStatement" type="button">Get statement</button><a id="stmtPdfLink" class="button" target="_blank" rel="noreferrer">PDF</a><pre id="stmtOut"></pre><h2>Balance alert</h2><input id="alertAddr" class="mono" placeholder="address" /><input id="alertThreshold" placeholder="threshold NET" /><button id="btnAlert" type="button">Save alert</button><button id="btnEvalAlerts" class="secondary" type="button">Evaluate alerts</button><p id="alertMsg" class="muted"></p><h2>Spending limits / savings mode</h2><input id="limitWallet" placeholder="wallet id or address" /><input id="singleLimit" placeholder="single tx limit NET" /><input id="dailyLimit" placeholder="daily limit NET" /><select id="limitMode"><option>daily</option><option>savings</option><option>business</option></select><button id="btnLimits" type="button">Save limits</button><p id="limitMsg" class="muted"></p></div></div>`));
    $("#btnStatement").onclick = async () => { try { const addr=encodeURIComponent($("#stmtAddr").value); const month=encodeURIComponent($("#stmtMonth").value); const r=await api(`/wallet/statement?address=${addr}&month=${month}`); $("#stmtOut").textContent=JSON.stringify(r,null,2); $("#stmtPdfLink").href=`/api/wallet/statement.pdf?address=${addr}&month=${month}`; } catch(e){ $("#stmtOut").textContent=e.message; } };
    $("#btnAlert").onclick = async () => { const msg=$("#alertMsg"); try { const r=await apiPost("/wallet/alerts", { address: $("#alertAddr").value, threshold: $("#alertThreshold").value, kind: "balance_below" }); msg.className="ok"; msg.textContent=`Saved alert ${r.alert_id}.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnEvalAlerts").onclick = async () => { const msg=$("#alertMsg"); try { const r=await apiPost("/wallet/alerts/evaluate", {}); msg.className="ok"; msg.textContent=`Triggered ${r.triggered} alert(s).`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnLimits").onclick = async () => { const msg=$("#limitMsg"); try { const r=await apiPost("/wallet/limits", { wallet_id: $("#limitWallet").value, single_tx_limit: $("#singleLimit").value, daily_limit: $("#dailyLimit").value, mode: $("#limitMode").value }); msg.className="ok"; msg.textContent=`Saved limits for ${r.wallet_id}.`; } catch(e){ msg.className="err"; msg.textContent=e.message; } };
    $("#btnTeam").onclick = async () => { try { const r=await apiPost("/wallet/team-wallets", { wallet_id: $("#teamId").value, name: $("#teamName").value, required_approvals: $("#teamRequired").value }); $("#teamOut").textContent=JSON.stringify(r,null,2); } catch(e){ $("#teamOut").textContent=e.message; } };
    $("#btnTeamProposal").onclick = async () => { try { const r=await apiPost(`/wallet/team-wallets/${encodeURIComponent($("#teamId").value)}/proposals`, { to_address: $("#teamTo").value, amount: $("#teamAmount").value }); $("#teamOut").textContent=JSON.stringify(r,null,2); } catch(e){ $("#teamOut").textContent=e.message; } };
  }


  async function phase7Page() {
    setView(el(`<div class="card muted">Loading Phase 7 app-layer contracts…</div>`));
    let templates = {}, recurring = [], escrows = [], polls = [], markets = [];
    try {
      const [tpl, rec, escrowsResp, pollsResp, marketsResp] = await Promise.all([
        api("/contracts/templates"), api("/recurring"), api("/escrows"), api("/polls"), api("/markets")
      ]);
      templates = tpl.templates || {}; recurring = rec.agreements || []; escrows = escrowsResp.escrows || []; polls = pollsResp.polls || []; markets = marketsResp.markets || [];
    } catch (e) {
      setView(el(`<div class="card err">Could not load Phase 7 data: ${esc(e.message)}</div>`)); return;
    }
    const tplRows = Object.values(templates).map((t) => `<tr><td>${esc(t.type)}</td><td>${esc(t.title)}</td><td>${esc(t.description)}</td></tr>`).join("");
    const recRows = recurring.map((r) => `<tr><td>${esc(r.label || r.agreement_id)}</td><td>${esc(r.amount)} NET</td><td>${esc(r.interval)}</td><td>${esc(r.status)}</td><td>${new Date((r.next_due_at || 0) * 1000).toLocaleString()}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">No recurring agreements yet.</td></tr>`;
    const escrowRows = escrows.map((r) => `<tr><td>${esc(r.escrow_id)}</td><td class="mono trunc">${esc(r.escrow_address)}</td><td>${esc(r.amount)} NET</td><td>${esc(r.status)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No escrow deals yet.</td></tr>`;
    const pollRows = polls.map((p) => `<tr><td>${esc(p.title)}</td><td>${esc(p.status)}</td><td>${p.vote_count || 0}</td><td><pre>${esc(JSON.stringify(p.results || {}, null, 2))}</pre></td></tr>`).join("") || `<tr><td colspan="4" class="muted">No polls yet.</td></tr>`;
    const marketRows = markets.map((m) => `<tr><td>${esc(m.question)}</td><td>${esc(m.mode)}</td><td>${esc(m.status)}</td><td>${(m.trades || []).length}</td><td>${esc(m.winning_outcome_id || "")}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">No prediction markets yet.</td></tr>`;
    setView(el(`<div>
      <div class="card"><h2>Phase 7: smart-contract templates</h2><p class="muted">These are app-layer templates first: they create descriptors, payout plans, agreements, votes, and market state without changing consensus rules.</p><table><thead><tr><th>Type</th><th>Name</th><th>Purpose</th></tr></thead><tbody>${tplRows}</tbody></table></div>
      <div class="card"><h2>Create timelock or multisig template</h2><input id="tlPub" class="mono" placeholder="public key for timelock" /><input id="tlHeight" placeholder="unlock height" /><input id="tlAmount" placeholder="amount NET" /><button id="btnTimelock" type="button">Create timelock</button><hr><input id="msPubs" class="mono" placeholder="comma-separated public keys" /><input id="msReq" placeholder="required signatures, e.g. 2" /><button id="btnMultisig" type="button">Create multisig</button><pre id="contractOut"></pre></div>
      <div class="card"><h2>Recurring payment agreements</h2><input id="rpPayer" class="mono" placeholder="payer address" /><input id="rpRecipient" class="mono" placeholder="recipient address" /><input id="rpAmount" placeholder="amount NET" /><select id="rpInterval"><option>monthly</option><option>weekly</option><option>daily</option><option>yearly</option></select><input id="rpMemo" placeholder="memo" /><button id="btnRecurring" type="button">Create agreement</button><table><thead><tr><th>Label</th><th>Amount</th><th>Interval</th><th>Status</th><th>Next due</th></tr></thead><tbody>${recRows}</tbody></table><pre id="recurringOut"></pre></div>
      <div class="card"><h2>2-of-3 escrow contracts</h2><input id="escBuyerPub" class="mono" placeholder="buyer public key" /><input id="escSellerPub" class="mono" placeholder="seller public key" /><input id="escMediatorPub" class="mono" placeholder="mediator public key" /><input id="escBuyerAddr" class="mono" placeholder="buyer refund address" /><input id="escSellerAddr" class="mono" placeholder="seller payout address" /><input id="escAmount" placeholder="amount NET" /><textarea id="escTerms" placeholder="deal terms"></textarea><button id="btnEscrow" type="button">Create escrow</button><table><thead><tr><th>ID</th><th>Escrow address</th><th>Amount</th><th>Status</th></tr></thead><tbody>${escrowRows}</tbody></table><pre id="escrowOut"></pre></div>
      <div class="card"><h2>Signed-message polls / voting</h2><input id="pollTitle" placeholder="poll title" /><input id="pollOptions" placeholder="comma-separated options, e.g. yes,no" /><button id="btnPoll" type="button">Create poll</button><p class="muted">Votes require signed messages through the API; demo clients may pass allow_unverified_demo for local testing.</p><table><thead><tr><th>Poll</th><th>Status</th><th>Votes</th><th>Results</th></tr></thead><tbody>${pollRows}</tbody></table><pre id="pollOut"></pre></div>
      <div class="card"><h2>Prediction-market demo</h2><p class="muted">Testnet/play-money only. Create YES/NO event markets, place demo orders, match trades, and resolve to a payout plan.</p><input id="mktQuestion" placeholder="market question" /><input id="mktOutcomes" placeholder="outcomes, e.g. YES,NO" value="YES,NO" /><input id="mktOracle" placeholder="oracle / resolver" value="manual" /><button id="btnMarket" type="button">Create market</button><hr><input id="orderMarket" placeholder="market id" /><input id="orderTrader" class="mono" placeholder="trader address" /><input id="orderOutcome" placeholder="outcome id, e.g. out1" /><select id="orderSide"><option>buy</option><option>sell</option></select><input id="orderQty" placeholder="quantity" /><input id="orderPrice" placeholder="price bps, e.g. 5000" /><button id="btnOrder" type="button">Place order</button><hr><input id="resolveMarket" placeholder="market id" /><input id="resolveOutcome" placeholder="winning outcome id" /><button id="btnResolve" class="secondary" type="button">Resolve market</button><table><thead><tr><th>Question</th><th>Mode</th><th>Status</th><th>Trades</th><th>Winner</th></tr></thead><tbody>${marketRows}</tbody></table><pre id="marketOut"></pre></div>
    </div>`));
    const out = (id, data) => { $(id).textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2); };
    $("#btnTimelock").onclick = async () => { try { out("#contractOut", await apiPost("/contracts", { type:"timelock", public_key:$("#tlPub").value, unlock_height:$("#tlHeight").value, amount:$("#tlAmount").value })); } catch(e){ out("#contractOut", e.message); } };
    $("#btnMultisig").onclick = async () => { try { out("#contractOut", await apiPost("/contracts", { type:"multisig", public_keys:$("#msPubs").value.split(",").map(x=>x.trim()).filter(Boolean), required_signatures:$("#msReq").value })); } catch(e){ out("#contractOut", e.message); } };
    $("#btnRecurring").onclick = async () => { try { out("#recurringOut", await apiPost("/recurring", { payer_address:$("#rpPayer").value, recipient_address:$("#rpRecipient").value, amount:$("#rpAmount").value, interval:$("#rpInterval").value, memo:$("#rpMemo").value })); } catch(e){ out("#recurringOut", e.message); } };
    $("#btnEscrow").onclick = async () => { try { out("#escrowOut", await apiPost("/escrows", { buyer_pubkey:$("#escBuyerPub").value, seller_pubkey:$("#escSellerPub").value, mediator_pubkey:$("#escMediatorPub").value, buyer_address:$("#escBuyerAddr").value, seller_address:$("#escSellerAddr").value, amount:$("#escAmount").value, terms:$("#escTerms").value })); } catch(e){ out("#escrowOut", e.message); } };
    $("#btnPoll").onclick = async () => { try { out("#pollOut", await apiPost("/polls", { title:$("#pollTitle").value, options:$("#pollOptions").value.split(",").map(x=>x.trim()).filter(Boolean) })); } catch(e){ out("#pollOut", e.message); } };
    $("#btnMarket").onclick = async () => { try { out("#marketOut", await apiPost("/markets", { question:$("#mktQuestion").value, outcomes:$("#mktOutcomes").value.split(",").map(x=>x.trim()).filter(Boolean), oracle:$("#mktOracle").value, mode:"testnet_demo" })); } catch(e){ out("#marketOut", e.message); } };
    $("#btnOrder").onclick = async () => { try { out("#marketOut", await apiPost(`/markets/${encodeURIComponent($("#orderMarket").value)}/order`, { trader_address:$("#orderTrader").value, outcome_id:$("#orderOutcome").value, side:$("#orderSide").value, quantity:$("#orderQty").value, price_bps:$("#orderPrice").value })); } catch(e){ out("#marketOut", e.message); } };
    $("#btnResolve").onclick = async () => { try { out("#marketOut", await apiPost(`/markets/${encodeURIComponent($("#resolveMarket").value)}/resolve`, { winning_outcome_id:$("#resolveOutcome").value, payout_per_share:"1" })); } catch(e){ out("#marketOut", e.message); } };
  }

  async function miningPage() {
    setView(el(`<div class="card muted">Loading mining dashboards…</div>`));
    try {
      const [dash, countdown, net] = await Promise.all([api("/mining/dashboard"), api("/reward-countdown"), api("/network")]);
      const rows = (dash.top_miners || []).map((m) => `<tr><td class="mono trunc">${addressLink(m.address)}</td><td class="right">${m.blocks}</td><td class="right acc">${m.reward} NET</td></tr>`).join("") || `<tr><td colspan="3" class="muted">No mined rewards yet.</td></tr>`;
      setView(el(`<div><div class="card"><h2>Network health</h2><div class="stats"><div class="stat"><div class="k">Height</div><div class="v">${net.height}</div></div><div class="stat"><div class="k">Peers</div><div class="v">${net.peer_count}</div></div><div class="stat"><div class="k">Mempool</div><div class="v">${net.mempool_transactions}</div></div><div class="stat"><div class="k">Avg interval</div><div class="v">${net.average_block_interval_seconds}s</div></div></div></div><div class="card"><h2>Reward countdown</h2><div class="kv"><div class="k">Next event</div><div class="v">${esc(countdown.next_event)}</div><div class="k">Event height</div><div class="v">${countdown.event_height}</div><div class="k">Blocks left</div><div class="v">${countdown.blocks_remaining}</div><div class="k">Current subsidy</div><div class="v acc">${countdown.current_subsidy} NET</div></div></div><div class="card"><h2>Mining dashboard</h2><table><thead><tr><th>Miner</th><th class="right">Blocks</th><th class="right">Rewards</th></tr></thead><tbody>${rows}</tbody></table></div><div class="card"><h2>Mining calculator</h2><input id="hashrate" placeholder="your hashrate" value="1" /><button id="btnCalcMining" type="button">Estimate</button><pre id="calcOut"></pre></div></div>`));
      $("#btnCalcMining").onclick = async () => { try { $("#calcOut").textContent = JSON.stringify(await api(`/mining/calculator?hashrate=${encodeURIComponent($("#hashrate").value)}`), null, 2); } catch(e){ $("#calcOut").textContent = e.message; } };
    } catch (e) { setView(el(`<div class="card err">Could not load mining data: ${esc(e.message)}</div>`)); }
  }

  function apiDocs() {
    setView(el(`<div class="card"><h2>Explorer / node API docs</h2><table><thead><tr><th>Endpoint</th><th>Description</th></tr></thead><tbody>
      <tr><td class="mono">/api/latest?n=15</td><td>Latest blocks and tip summary.</td></tr>
      <tr><td class="mono">/api/block/&lt;hash&gt;</td><td>Block header and transactions.</td></tr>
      <tr><td class="mono">/api/tx/&lt;txid&gt;</td><td>Transaction decode and confirmation status.</td></tr>
      <tr><td class="mono">/api/address/&lt;address&gt;</td><td>Address balance and transaction ids.</td></tr>
      <tr><td class="mono">/api/mempool</td><td>Unconfirmed transactions, package groups, fee rates, and RBF flag.</td></tr>
      <tr><td class="mono">/api/fee-estimates</td><td>Slow/normal/fast local fee estimates.</td></tr>
      <tr><td class="mono">/api/headers?start=0&amp;limit=100</td><td>Header data used by network stats/difficulty views.</td></tr>
      <tr><td class="mono">/api/peers</td><td>Peer list and scores if exposed by the backing node.</td></tr>
      <tr><td class="mono">/api/latest-txs?n=20</td><td>Newest confirmed and mempool transactions.</td></tr>
      <tr><td class="mono">/api/invoices</td><td>Create/list payment requests and checkout status.</td></tr>
      <tr><td class="mono">/api/receipt/&lt;txid&gt;</td><td>Shareable transaction receipt data.</td></tr>
      <tr><td class="mono">/api/usernames</td><td>Local username/profile registry.</td></tr>
      <tr><td class="mono">/api/merchant/webhooks</td><td>Merchant webhook subscriptions and event log.</td></tr>
      <tr><td class="mono">/api/community/gifts</td><td>Gift-link creation and claim status.</td></tr>
      <tr><td class="mono">/api/wallet/statement</td><td>Wallet accounting statement by address.</td></tr>
      <tr><td class="mono">/api/contracts/templates</td><td>Phase 7 contract template registry.</td></tr>
      <tr><td class="mono">/api/recurring</td><td>Recurring payment agreements and due invoices.</td></tr>
      <tr><td class="mono">/api/escrows</td><td>2-of-3 escrow contract records and payout plans.</td></tr>
      <tr><td class="mono">/api/polls</td><td>Signed-message polls and vote results.</td></tr>
      <tr><td class="mono">/api/markets</td><td>Testnet/play-money prediction market demo state.</td></tr>
      <tr><td class="mono">/api/network</td><td>Network health dashboard data.</td></tr>
      <tr><td class="mono">/faucet/status</td><td>Optional same-origin faucet health endpoint.</td></tr>
    </tbody></table></div>`));
  }

  // ---------- search ----------
  async function doSearch(qRaw) {
    const q = qRaw.trim(); if (!q) return;
    try {
      if (/^\d+$/.test(q)) { // height
        const d = await api(`/headers?start=${q}&limit=1`);
        const hh = (d.headers || d)[0];
        if (hh && hh.hash) return (location.hash = "#/block/" + hh.hash);
        throw new Error("height not found");
      }
      if (q.startsWith("net1") || /^[A-Za-z0-9]{26,40}$/.test(q) && !/^[0-9a-fA-F]{64}$/.test(q)) {
        return (location.hash = "#/address/" + q); // address
      }
      if (/^[0-9a-fA-F]{64}$/.test(q)) { // block hash or txid
        try { await api("/block/" + q); return (location.hash = "#/block/" + q); }
        catch { return (location.hash = "#/tx/" + q); }
      }
      location.hash = "#/address/" + q;
    } catch (e) { setView(el(`<div class="card err">No result for “${esc(q)}”: ${esc(e.message)}</div>`)); }
  }

  // ---------- router ----------
  function route() {
    if (location.hash === "#/mempool") return mempool();
    if (location.hash === "#/fees") return fees();
    if (location.hash === "#/peers") return peers();
    if (location.hash === "#/stats") return networkStats();
    if (location.hash === "#/faucet") return faucetStatus();
    if (location.hash === "#/payments") return paymentsPage();
    if (location.hash === "#/pos") return posPage();
    if (location.hash === "#/names") return namesPage();
    if (location.hash === "#/merchant") return merchantPage();
    if (location.hash === "#/community") return communityPage();
    if (location.hash === "#/wallet-tools") return walletToolsPage();
    if (location.hash === "#/phase7") return phase7Page();
    if (location.hash === "#/mining") return miningPage();
    if (location.hash === "#/api") return apiDocs();
    const checkoutMatch = location.hash.match(/^#\/checkout\/(.+)$/);
    if (checkoutMatch) return checkoutPage(decodeURIComponent(checkoutMatch[1]));
    const receiptMatch = location.hash.match(/^#\/receipt\/(.+)$/);
    if (receiptMatch) return receiptPage(decodeURIComponent(receiptMatch[1]));
    const profileMatch = location.hash.match(/^#\/u\/(.+)$/);
    if (profileMatch) return profilePage(decodeURIComponent(profileMatch[1]));
    const m = location.hash.match(/^#\/(block|address|tx)\/(.+)$/);
    if (!m) return home();
    const [, kind, val] = m;
    if (kind === "block") return block(val);
    if (kind === "address") return address(decodeURIComponent(val));
    if (kind === "tx") return tx(val);
  }

  $("#home").onclick = () => { location.hash = ""; };
  $("#navHome").onclick = () => { location.hash = ""; };
  $("#navMempool").onclick = () => { location.hash = "#/mempool"; };
  $("#navFees").onclick = () => { location.hash = "#/fees"; };
  $("#navPeers").onclick = () => { location.hash = "#/peers"; };
  $("#navStats").onclick = () => { location.hash = "#/stats"; };
  $("#navFaucet").onclick = () => { location.hash = "#/faucet"; };
  $("#navPayments").onclick = () => { location.hash = "#/payments"; };
  $("#navPos").onclick = () => { location.hash = "#/pos"; };
  $("#navNames").onclick = () => { location.hash = "#/names"; };
  $("#navMerchant").onclick = () => { location.hash = "#/merchant"; };
  $("#navCommunity").onclick = () => { location.hash = "#/community"; };
  $("#navWalletTools").onclick = () => { location.hash = "#/wallet-tools"; };
  $("#navPhase7").onclick = () => { location.hash = "#/phase7"; };
  const navAdmin = $("#navAdmin"); if (navAdmin) navAdmin.onclick = () => { location.href = "admin.html"; };
  $("#navMining").onclick = () => { location.hash = "#/mining"; };
  $("#navApi").onclick = () => { location.hash = "#/api"; };
  $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(e.target.value); });
  $("#contactSelect").addEventListener("change", syncContactFormFromSelect);
  $("#contactAddress").addEventListener("input", syncContactNameFromAddress);
  $("#btnViewContact").onclick = viewSelectedContact;
  $("#btnSaveContact").onclick = saveContactFromFields;
  $("#btnDeleteContact").onclick = deleteSelectedContact;
  renderContacts();
  function startLiveUpdates() {
    if (!("EventSource" in window)) return;
    try {
      const es = new EventSource(API + "/events/stream");
      es.addEventListener("netcoin", () => { if (!location.hash || location.hash === "#/mempool" || location.hash === "#/stats") route(); });
      es.onerror = () => { es.close(); };
    } catch { /* polling fallback remains active */ }
  }
  startLiveUpdates();
  window.addEventListener("hashchange", route);
  $("#footer").textContent = "NetCoin Explorer · live data via same-origin relay · read-only";
  route();
  // auto-refresh the home view
  setInterval(() => { if (!location.hash) route(); }, 12000);
})();
