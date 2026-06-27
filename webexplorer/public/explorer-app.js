/* NetCoin Explorer — live, read-only. Talks only to a same-origin relay (/api/*)
   that proxies the node. No secrets, no writes. */
"use strict";
(function () {
  const API = (location.origin + "/api").replace(/\/$/, "");
  const COIN = 100000000;
  // NetCoin emission params (display only; mirror netcoin/params.py).
  const ACTIVATION = 1000, LEGACY_SUBSIDY = 50, EMISSION_BASE = 15, YEAR = 720;

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
  const view = $("#view");
  const setView = (node) => { view.replaceChildren(node); };

  // ---------- emission / supply panel ----------
  function subsidyAt(height) { return height < ACTIVATION ? LEGACY_SUBSIDY : EMISSION_BASE; }
  function emissionCard(height) {
    const toAct = Math.max(0, ACTIVATION - height);
    const pct = Math.min(100, (height / ACTIVATION) * 100);
    const minted = height * LEGACY_SUBSIDY; // pre-activation estimate (50 NET/block)
    const status = height < ACTIVATION
      ? `Legacy subsidy <b class="acc">${LEGACY_SUBSIDY} NET</b>/block — random emission activates at height ${ACTIVATION} (<b>${toAct}</b> blocks to go).`
      : `Random emission <b class="acc">active</b> — base ${EMISSION_BASE} NET/block, with a yearly random 10% "cut" (testnet year = ${YEAR} blocks).`;
    return el(`<div class="card">
      <h2>Emission</h2>
      <div class="muted" style="margin-bottom:10px">${status}</div>
      <div class="bar"><i style="width:${pct.toFixed(1)}%"></i></div>
      <div class="muted" style="margin-top:6px">~${minted.toLocaleString()} NET minted${height < ACTIVATION ? " (est.)" : ""} · current subsidy ${subsidyAt(height)} NET/block</div>
    </div>`);
  }

  // ---------- home ----------
  async function home() {
    let info, latest;
    try { info = (await api("/info")).node; latest = await api("/latest?n=15"); }
    catch (e) { setView(el(`<div class="card err">Cannot reach the node: ${esc(e.message)}</div>`)); return; }

    const stats = el(`<div class="stats">
      <div class="stat"><div class="k">Height</div><div class="v">${info.height.toLocaleString()}</div></div>
      <div class="stat"><div class="k">Mempool</div><div class="v">${info.mempool_transactions ?? 0}</div></div>
      <div class="stat"><div class="k">Difficulty (bits)</div><div class="v mono" style="font-size:14px">0x${(info.bits>>>0).toString(16)}</div></div>
      <div class="stat"><div class="k">Subsidy</div><div class="v">${subsidyAt(info.height)} <span class="muted" style="font-size:13px">NET</span></div></div>
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

    const frag = document.createDocumentFragment();
    frag.append(stats, emissionCard(info.height), blocks);
    setView(frag);
  }

  // ---------- block ----------
  async function block(hash) {
    setView(el(`<div class="card muted">Loading block…</div>`));
    let b; try { b = await api("/block/" + hash); } catch (e) { return setView(el(`<div class="card err">Block not found: ${esc(e.message)}</div>`)); }
    const h = b.header || {};
    const coinbaseOut = (b.transactions?.[0]?.outputs || []).reduce((s, o) => s + (o.amount || 0), 0);
    const txRows = (b.transactions || []).map((t, i) => {
      const outs = (t.outputs || []).map((o) => `<div class="mono trunc"><a href="#/address/${esc(o.address)}">${esc(o.address)}</a> · <span class="acc">${fmtNet(o.amount)} NET</span></div>`).join("");
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
        </div></div>
      <div class="card"><h2>Transactions (${(b.transactions||[]).length})</h2>
        <table><tbody>${txRows}</tbody></table></div></div>`));
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
      <div class="card"><h2>Address</h2>
        <div class="mono" style="word-break:break-all;margin-bottom:12px">${esc(a.address)}</div>
        <div class="stats">
          <div class="stat"><div class="k">Total</div><div class="v acc">${fmtNet(bal.total||0)} NET</div></div>
          <div class="stat"><div class="k">Spendable</div><div class="v">${fmtNet(bal.spendable||0)} NET</div></div>
          <div class="stat"><div class="k">Immature</div><div class="v warn">${fmtNet(bal.immature||0)} NET</div></div>
          <div class="stat"><div class="k">Txs</div><div class="v">${a.transaction_count ?? txids.length}</div></div>
        </div></div>
      <div class="card"><h2>Recent transactions</h2><table><tbody>${txRows}</tbody></table></div></div>`));
    $("#bk").onclick = () => history.back();
  }

  // ---------- tx ----------
  async function tx(txid) {
    setView(el(`<div class="card muted">Loading transaction…</div>`));
    let t; try { t = await api("/tx/" + txid); } catch (e) { return setView(el(`<div class="card err">Transaction not found: ${esc(e.message)}</div>`)); }
    const d = t.transaction || t;
    const outs = (d.outputs || []).map((o) => `<tr><td class="mono trunc"><a href="#/address/${esc(o.address)}">${esc(o.address)}</a></td><td class="right acc">${fmtNet(o.amount)} NET</td></tr>`).join("");
    const ins = (d.inputs || []).map((i) => `<tr><td class="mono trunc">${i.coinbase ? '<span class="acc">coinbase</span>' : esc((i.txid||"")+":"+i.vout)}</td></tr>`).join("");
    setView(el(`<div>
      <div class="back" id="bk">← back</div>
      <div class="card"><h2>Transaction</h2>
        <div class="mono" style="word-break:break-all">${esc(txid)}</div>
        ${t.block_hash ? `<div class="muted" style="margin-top:6px">in block <a href="#/block/${esc(t.block_hash)}">${trunc(t.block_hash,18)}</a> · height ${t.height ?? ""}</div>` : ""}</div>
      <div class="card"><h2>Inputs</h2><table><tbody>${ins||'<tr><td class="muted">—</td></tr>'}</tbody></table></div>
      <div class="card"><h2>Outputs</h2><table><tbody>${outs}</tbody></table></div></div>`));
    $("#bk").onclick = () => history.back();
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
    const m = location.hash.match(/^#\/(block|address|tx)\/(.+)$/);
    if (!m) return home();
    const [, kind, val] = m;
    if (kind === "block") return block(val);
    if (kind === "address") return address(decodeURIComponent(val));
    if (kind === "tx") return tx(val);
  }

  $("#home").onclick = () => { location.hash = ""; };
  $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(e.target.value); });
  window.addEventListener("hashchange", route);
  $("#footer").textContent = "NetCoin Explorer · live data via same-origin relay · read-only";
  route();
  // auto-refresh the home view
  setInterval(() => { if (!location.hash) route(); }, 12000);
})();
