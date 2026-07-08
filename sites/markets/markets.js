"use strict";

(() => {
  const $ = (sel) => document.querySelector(sel);
  const state = { markets: [], selectedId: "", apiOk: false, view: "grid", category: "All", query: "", tab: "orderbook", tradeSide: "yes", tradeOutcomeId: "" };
  const apiBase = localStorage.getItem("netcoinApiBase") || "/api";

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const fmtTime = (ts) => { if (!ts) return "n/a"; const n = Number(ts); return Number.isFinite(n) ? new Date(n * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : esc(ts); };

  function log(msg, payload) {
    const box = $("#activityLog"); if (!box) return;
    const extra = payload ? `\n${JSON.stringify(payload, null, 2)}` : "";
    box.textContent = `[${new Date().toLocaleTimeString()}] ${msg}${extra}\n\n${box.textContent}`.slice(0, 9000);
  }

  async function api(path, options = {}) {
    const res = await fetch(`${apiBase}${path}`, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    const text = await res.text();
    let payload; try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text }; }
    if (!res.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${res.status}`);
    return payload;
  }
  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

  const selectedMarket = () => state.markets.find((m) => m.market_id === state.selectedId) || null;
  const isBinary = (m) => (m.outcomes || []).length === 2 && (m.outcomes || []).some((o) => /^y(es)?$/i.test(o.label));
  const yesOutcome = (m) => (m.outcomes || []).find((o) => /^y(es)?$/i.test(o.label)) || (m.outcomes || [])[0];
  const noOutcome = (m) => (m.outcomes || []).find((o) => /^n(o)?$/i.test(o.label)) || (m.outcomes || [])[1];

  // probability (0..100 cents) for an outcome, from ticker -> clob -> implied stats
  function centsFor(m, oid) {
    const t = ((m.ticker || {}).outcomes || []).find((o) => o.outcome_id === oid);
    if (t) {
      if (t.price_bps != null) return Math.round(Number(t.price_bps) / 100);
      if (t.price != null) return Math.round(Number(t.price) * 100);
    }
    const ip = ((m.stats || {}).implied_probabilities || {})[oid];
    if (ip && ip.probability != null) { const p = Number(String(ip.probability).replace("%", "")); return p <= 1 ? Math.round(p * 100) : Math.round(p); }
    return null;
  }
  function bestAskCents(m, oid) {
    const book = ((m.clob || {}).books || {})[oid] || (m.orderbook || {})[oid];
    if (book && book.best_ask_bps != null) return Math.round(Number(book.best_ask_bps) / 100);
    if (book && book.best_ask != null) return Math.round(Number(book.best_ask) * 100);
    return centsFor(m, oid);
  }
  // display price with binary complement (No = 100 - Yes when No has no direct quote)
  function displayCents(m, oid) {
    const direct = centsFor(m, oid);
    if (direct != null) return direct;
    if (isBinary(m)) {
      const yo = yesOutcome(m), no = noOutcome(m);
      if (no && oid === no.outcome_id) { const y = centsFor(m, yo.outcome_id); if (y != null) return 100 - y; }
      if (yo && oid === yo.outcome_id) { const n = centsFor(m, no.outcome_id); if (n != null) return 100 - n; }
    }
    return null;
  }
  const fmtCents = (c) => (c == null ? "—" : `${c}¢`);
  const fmtPct = (c) => (c == null ? "—" : `${c}%`);

  /* ---------------- grid view ---------------- */
  function categories() {
    const set = new Set(["All"]);
    state.markets.forEach((m) => { if (m.category) set.add(String(m.category)); });
    return [...set];
  }
  function renderChips() {
    $("#categoryChips").innerHTML = categories().map((c) =>
      `<button class="chip${c === state.category ? " active" : ""}" type="button" data-cat="${esc(c)}">${esc(c)}</button>`).join("");
    $("#categoryChips").querySelectorAll("[data-cat]").forEach((b) => b.addEventListener("click", () => { state.category = b.getAttribute("data-cat"); renderGrid(); renderChips(); }));
  }
  function renderMetrics(totals) {
    const s = totals || {};
    const rows = [
      ["Markets", s.count ?? state.markets.length],
      ["Open", s.open ?? state.markets.filter((m) => m.status === "open").length],
      ["Resolved", s.resolved ?? state.markets.filter((m) => m.status === "resolved").length],
      ["Volume", s.volume || "0"],
    ];
    $("#marketMetrics").innerHTML = rows.map(([k, v]) => `<div class="mkt-metric"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("");
  }
  function visibleMarkets() {
    const q = state.query.trim().toLowerCase();
    return state.markets.filter((m) =>
      (state.category === "All" || String(m.category) === state.category) &&
      (!q || String(m.question).toLowerCase().includes(q)));
  }
  function cardHtml(m) {
    const avatar = esc(String(m.question || "?").trim().charAt(0).toUpperCase() || "N");
    const vol = ((m.stats || {}).volume) || m.volume || "0";
    const foot = `<div class="mkt-foot"><span>Vol ${esc(vol)}</span><span>${m.status === "open" ? `closes ${fmtTime(m.close_time)}` : esc(m.status)}</span></div>`;
    const head = `<div class="mkt-card-head"><div class="mkt-avatar">${avatar}</div><div class="mkt-q">${esc(m.question)}</div></div>`;
    if (isBinary(m)) {
      const yo = yesOutcome(m); const c = displayCents(m, yo.outcome_id);
      return `<div class="mkt-card" data-id="${esc(m.market_id)}">${head}
        <div class="mkt-binary">
          <div class="mkt-chance"><span class="pct">${fmtPct(c)}</span><span class="lbl">chance</span></div>
          <div class="yn-btns"><button class="yn yn-yes" data-buy="yes" data-id="${esc(m.market_id)}">Yes ${fmtCents(displayCents(m, yo.outcome_id))}</button><button class="yn yn-no" data-buy="no" data-id="${esc(m.market_id)}">No ${fmtCents(displayCents(m, (noOutcome(m) || {}).outcome_id))}</button></div>
        </div>
        <div class="mkt-prob-bar"><span style="width:${c == null ? 0 : c}%"></span></div>${foot}</div>`;
    }
    const rows = (m.outcomes || []).slice(0, 4).map((o) => `<div class="mkt-outcome-row"><span class="name">${esc(o.label)}</span><span class="op">${fmtPct(displayCents(m, o.outcome_id))}</span></div>`).join("");
    return `<div class="mkt-card" data-id="${esc(m.market_id)}">${head}<div class="mkt-outcomes">${rows}</div>${foot}</div>`;
  }
  function renderGrid() {
    const grid = $("#marketGrid");
    const list = visibleMarkets();
    if (!state.apiOk) { grid.innerHTML = `<div class="empty-state">Could not reach the NetCoin API at ${esc(apiBase)}. Start a node/explorer server and refresh.</div>`; return; }
    if (!list.length) { grid.innerHTML = `<div class="empty-state">No markets yet. Open Operator tools to create one.</div>`; return; }
    grid.innerHTML = list.map(cardHtml).join("");
    grid.querySelectorAll(".mkt-card").forEach((el) => el.addEventListener("click", (e) => {
      if (e.target.closest("[data-buy]")) return;
      openDetail(el.getAttribute("data-id"));
    }));
    grid.querySelectorAll("[data-buy]").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      state.tradeSide = b.getAttribute("data-buy");
      openDetail(b.getAttribute("data-id"));
    }));
  }

  /* ---------------- detail view ---------------- */
  function sparkline(m) {
    const points = (((m.analytics || {}).price_points) || []).slice(-60);
    if (points.length < 2) return `<p class="muted" style="padding:8px 0">Price history appears here once this market has a few trades.</p>`;
    const w = 640, h = 160, pad = 8;
    const coords = points.map((p, i) => {
      const x = pad + (i * (w - 2 * pad) / Math.max(1, points.length - 1));
      const y = h - pad - ((Number(p.price_bps || 0) / 10000) * (h - 2 * pad));
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<svg class="sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Price history"><polyline points="${coords}" fill="none" stroke="currentColor" stroke-width="2.5"/></svg>`;
  }
  function bookTab(m) {
    return (m.outcomes || []).map((o) => {
      const book = ((m.clob || {}).books || {})[o.outcome_id] || {};
      const ob = (m.orderbook || {})[o.outcome_id] || { buys: [], sells: [] };
      const maxRows = Math.max((ob.buys || []).length, (ob.sells || []).length, 1);
      const rows = Array.from({ length: Math.min(maxRows, 8) }, (_, i) => {
        const bid = (ob.buys || [])[i], ask = (ob.sells || [])[i];
        return `<tr><td class="book-bid">${bid ? `${esc(bid.price)} × ${esc(bid.remaining)} <button class="mini-cancel" data-cancel="${esc(bid.order_id)}">×</button>` : ""}</td><td class="book-ask">${ask ? `${esc(ask.price)} × ${esc(ask.remaining)} <button class="mini-cancel" data-cancel="${esc(ask.order_id)}">×</button>` : ""}</td></tr>`;
      }).join("");
      return `<h4 style="margin:12px 0 6px">${esc(o.label)} <span class="muted">mid ${esc(book.midpoint || "—")} · spread ${esc(book.spread || "—")}</span></h4><table class="book-tbl"><thead><tr><th>Bids (price × shares)</th><th>Asks (price × shares)</th></tr></thead><tbody>${rows}</tbody></table>`;
    }).join("");
  }
  function tradesTab(m) {
    const trades = (m.trades || []).slice(-15).reverse();
    if (!trades.length) return `<p class="muted">No trades yet.</p>`;
    return `<table class="book-tbl"><thead><tr><th>Time</th><th>Outcome</th><th>Price</th><th>Shares</th></tr></thead><tbody>${trades.map((t) => `<tr><td>${fmtTime(t.created_at)}</td><td>${esc(t.outcome_id)}</td><td>${esc(t.price || (Number(t.price_bps || 0) / 10000).toFixed(2))}</td><td>${esc(t.quantity)}</td></tr>`).join("")}</tbody></table>`;
  }
  function holdersTab(m) {
    const ports = (((m.portfolio || {}).portfolios) || []).slice(0, 12);
    if (!ports.length) return `<p class="muted">Positions appear after trades.</p>`;
    return `<table class="book-tbl"><thead><tr><th>Trader</th><th>Equity</th><th>Positions</th></tr></thead><tbody>${ports.map((p) => {
      const pos = (p.positions || []).filter((x) => Number(x.quantity || 0) !== 0).map((x) => `${esc(x.label)}:${esc(x.quantity)}`).join(" · ") || "—";
      return `<tr><td class="mono">${esc(p.trader_id)}</td><td>${esc(p.equity || "0")}</td><td>${pos}</td></tr>`;
    }).join("")}</tbody></table>`;
  }
  function rulesTab(m) {
    const wf = m.resolution_workflow || {};
    const evidence = (m.resolution_evidence || []).slice(-5).reverse();
    const ev = evidence.length ? evidence.map((e) => `<li><b>${esc(e.title || e.source_type || "evidence")}</b> — ${esc(e.url || e.statement || "manual note")} <span class="muted">${fmtTime(e.created_at || e.timestamp)}</span></li>`).join("") : `<li class="muted">No evidence yet.</li>`;
    return `<p class="muted">Status: ${esc(wf.status || "unresolved")} · Oracle: ${esc(wf.optimistic_oracle_status || "unproposed")} · Source: ${esc(m.resolution_source || wf.evidence_url || "manual operator review")}</p>
      <p>${esc(m.rules || m.warning || "Testnet/play-money market. Resolves by manual operator review with an evidence trail.")}</p>
      <h4 style="margin:12px 0 6px">Evidence</h4><ul>${ev}</ul>`;
  }
  function tradePanel(m) {
    const binary = isBinary(m);
    let outcomeId = state.tradeOutcomeId;
    if (binary) outcomeId = state.tradeSide === "no" ? (noOutcome(m) || {}).outcome_id : (yesOutcome(m) || {}).outcome_id;
    else if (!outcomeId || !(m.outcomes || []).some((o) => o.outcome_id === outcomeId)) outcomeId = ((m.outcomes || [])[0] || {}).outcome_id;
    state.tradeOutcomeId = outcomeId;
    const priceC = bestAskCents(m, outcomeId) ?? 50;
    const resolved = m.status !== "open";
    const sideRow = binary
      ? `<div class="side-toggle"><button type="button" data-side="yes" class="${state.tradeSide === "yes" ? "sel-yes" : ""}">Yes ${fmtCents(displayCents(m, (yesOutcome(m) || {}).outcome_id))}</button><button type="button" data-side="no" class="${state.tradeSide === "no" ? "sel-no" : ""}">No ${fmtCents(displayCents(m, (noOutcome(m) || {}).outcome_id))}</button></div>`
      : `<div class="trade-field"><label>Outcome</label><select id="tradeOutcome">${(m.outcomes || []).map((o) => `<option value="${esc(o.outcome_id)}"${o.outcome_id === outcomeId ? " selected" : ""}>${esc(o.label)} · ${fmtCents(displayCents(m, o.outcome_id))}</option>`).join("")}</select></div>`;
    const noSide = binary && state.tradeSide === "no";
    return `<h3>${resolved ? "Market closed" : "Buy shares"}</h3>
      ${sideRow}
      <div class="trade-field"><label>Shares</label><input id="tradeShares" type="number" min="1" value="5" ${resolved ? "disabled" : ""} /></div>
      <div class="trade-field"><label>Limit price (¢)</label><input id="tradePrice" type="number" min="1" max="99" value="${priceC}" ${resolved ? "disabled" : ""} /></div>
      <div class="trade-summary">
        <div class="row"><span>Avg price</span><b id="sumPrice">${priceC}¢</b></div>
        <div class="row"><span>Cost</span><b id="sumCost">—</b></div>
        <div class="row"><span>Payout if wins</span><b id="sumPayout">—</b></div>
      </div>
      <button class="buy-btn ${noSide ? "no" : ""}" id="tradeBuy" ${resolved ? "disabled" : ""}>${resolved ? "Resolved" : `Buy ${binary ? (noSide ? "No" : "Yes") : "shares"}`}</button>
      <details class="trade-adv"><summary>Advanced</summary><div class="adv-body">
        <div class="trade-field"><label>Trader id</label><input id="tradeTrader" value="demo:you" /></div>
        <div class="trade-field"><label>Order type</label><select id="tradeType"><option value="limit">Limit</option><option value="market">Market</option><option value="ioc">IOC</option><option value="fok">FOK</option></select></div>
      </div></details>
      <p class="muted" style="font-size:12px">Play-money. Buys place a NET limit order on this outcome.</p>`;
  }
  function updateTradeSummary() {
    const shares = Number(($("#tradeShares") || {}).value || 0);
    const priceC = Number(($("#tradePrice") || {}).value || 0);
    if ($("#sumPrice")) $("#sumPrice").textContent = `${priceC}¢`;
    if ($("#sumCost")) $("#sumCost").textContent = `${(shares * priceC / 100).toFixed(2)} NET`;
    if ($("#sumPayout")) $("#sumPayout").textContent = `${(shares * 1).toFixed(2)} NET`;
  }
  function renderDetail() {
    const m = selectedMarket();
    if (!m) { backToGrid(); return; }
    const avatar = esc(String(m.question || "?").trim().charAt(0).toUpperCase() || "N");
    const yc = isBinary(m) ? displayCents(m, (yesOutcome(m) || {}).outcome_id) : null;
    const s = m.stats || {};
    $("#detailMain").innerHTML = `
      <div class="detail-head"><div class="mkt-avatar">${avatar}</div><div><h1>${esc(m.question)}</h1>
        <div class="detail-sub"><span>Vol ${esc(s.volume || "0")}</span><span>Liquidity ${esc(s.liquidity_shares || 0)}</span><span>${m.status === "open" ? `closes ${fmtTime(m.close_time)}` : esc(m.status)}</span></div></div></div>
      <div class="detail-card">
        <div class="chart-hero">${yc != null ? `<span class="big">${yc}%</span><span class="cap">Yes · chance</span>` : `<span class="cap">Outcome prices</span>`}</div>
        ${sparkline(m)}
      </div>
      <div class="detail-card">
        <div class="mkt-tabs">
          <button class="mkt-tab${state.tab === "orderbook" ? " active" : ""}" data-tab="orderbook">Order book</button>
          <button class="mkt-tab${state.tab === "trades" ? " active" : ""}" data-tab="trades">Trades</button>
          <button class="mkt-tab${state.tab === "holders" ? " active" : ""}" data-tab="holders">Holders</button>
          <button class="mkt-tab${state.tab === "rules" ? " active" : ""}" data-tab="rules">Rules</button>
        </div>
        <div class="tab-panel${state.tab === "orderbook" ? " active" : ""}" data-panel="orderbook">${bookTab(m)}</div>
        <div class="tab-panel${state.tab === "trades" ? " active" : ""}" data-panel="trades">${tradesTab(m)}</div>
        <div class="tab-panel${state.tab === "holders" ? " active" : ""}" data-panel="holders">${holdersTab(m)}</div>
        <div class="tab-panel${state.tab === "rules" ? " active" : ""}" data-panel="rules">${rulesTab(m)}</div>
      </div>`;
    $("#tradePanel").innerHTML = tradePanel(m);
    wireDetail(m);
    renderOutcomeSelectors(m);
    updateTradeSummary();
  }
  function wireDetail(m) {
    $("#detailMain").querySelectorAll(".mkt-tab").forEach((b) => b.addEventListener("click", () => {
      state.tab = b.getAttribute("data-tab");
      $("#detailMain").querySelectorAll(".mkt-tab").forEach((x) => x.classList.toggle("active", x === b));
      $("#detailMain").querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.getAttribute("data-panel") === state.tab));
    }));
    $("#detailMain").querySelectorAll("[data-cancel]").forEach((b) => b.addEventListener("click", () => cancelOrder(b.getAttribute("data-cancel"))));
    const panel = $("#tradePanel");
    panel.querySelectorAll("[data-side]").forEach((b) => b.addEventListener("click", () => { state.tradeSide = b.getAttribute("data-side"); $("#tradePanel").innerHTML = tradePanel(m); wireDetail(m); updateTradeSummary(); }));
    const to = $("#tradeOutcome"); if (to) to.addEventListener("change", () => { state.tradeOutcomeId = to.value; $("#tradePrice") ; $("#tradePanel").innerHTML = tradePanel(m); wireDetail(m); updateTradeSummary(); });
    ["tradeShares", "tradePrice"].forEach((id) => { const el = $("#" + id); if (el) el.addEventListener("input", updateTradeSummary); });
    const buy = $("#tradeBuy"); if (buy) buy.addEventListener("click", () => doTradeBuy(m));
  }
  async function doTradeBuy(m) {
    try {
      const type = ($("#tradeType") || {}).value || "limit";
      const priceC = Number(($("#tradePrice") || {}).value || 0);
      await placeOrder({
        trader_address: ($("#tradeTrader") || {}).value || "demo:you",
        outcome_id: state.tradeOutcomeId,
        side: "buy",
        order_type: type,
        time_in_force: type === "ioc" ? "IOC" : type === "fok" ? "FOK" : "GTC",
        quantity: Number(($("#tradeShares") || {}).value || 0),
        price_bps: type === "market" ? undefined : Math.max(1, Math.min(9999, priceC * 100)),
        allow_unverified_demo: true,
        sandbox_short_mode: true,
      });
    } catch (err) { alert(`Order failed: ${err.message}`); }
  }

  function openDetail(id) { state.selectedId = id; state.view = "detail"; state.tab = "orderbook"; state.tradeOutcomeId = ""; $("#gridView").classList.add("hidden"); $("#detailView").classList.remove("hidden"); renderDetail(); window.scrollTo(0, 0); }
  function backToGrid() { state.view = "grid"; $("#detailView").classList.add("hidden"); $("#gridView").classList.remove("hidden"); }

  function renderOutcomeSelectors(m) {
    const opts = (m?.outcomes || []).map((o) => `<option value="${esc(o.outcome_id)}">${esc(o.label)}</option>`).join("");
    if ($("#orderOutcome")) $("#orderOutcome").innerHTML = opts || `<option value="">Select market</option>`;
    if ($("#resolveOutcome")) $("#resolveOutcome").innerHTML = opts || `<option value="">Select market</option>`;
  }

  function renderAll(totals) { renderMetrics(totals); renderChips(); if (state.view === "grid") renderGrid(); else renderDetail(); }

  /* ---------------- API actions (unchanged wiring) ---------------- */
  async function loadMarkets() {
    try {
      const payload = await api("/markets");
      state.markets = payload.markets || [];
      if (!state.selectedId && state.markets[0]) state.selectedId = state.markets[0].market_id;
      state.apiOk = true;
      $("#apiStatus").textContent = `live${payload.warning ? " · " + payload.warning : ""}`;
      renderAll(payload.totals);
    } catch (err) {
      state.apiOk = false;
      $("#apiStatus").textContent = `API offline`;
      renderMetrics({ count: 0, open: 0, resolved: 0, volume: "0" });
      renderGrid();
      log("Market load failed", { error: err.message });
    }
  }
  async function createMarket(body) { const p = await post("/markets", body); log("Created market", { market_id: p.market_id }); state.selectedId = p.market_id; await loadMarkets(); }
  async function placeOrder(body) { const m = selectedMarket(); if (!m) throw new Error("Select a market first"); const p = await post(`/markets/${encodeURIComponent(m.market_id)}/order`, body); log("Placed order", { trades: (p.trades || []).length }); await loadMarkets(); }
  async function cancelOrder(orderId) { const m = selectedMarket(); if (!m || !orderId) return; await post(`/markets/${encodeURIComponent(m.market_id)}/orders/${encodeURIComponent(orderId)}/cancel`, { operator_override: true }); log("Canceled order", { order_id: orderId }); await loadMarkets(); }
  async function resolveMarket(requestOnly) {
    const m = selectedMarket(); if (!m) throw new Error("Select a market first");
    const body = { winning_outcome_id: $("#resolveOutcome").value, evidence_url: $("#evidenceUrl").value, resolution_note: $("#evidenceUrl").value, payout_per_share: m.unit_payout || "1", operator_approved: !requestOnly };
    const path = requestOnly ? `/markets/${encodeURIComponent(m.market_id)}/resolution-request` : `/markets/${encodeURIComponent(m.market_id)}/resolve`;
    const p = await post(path, body); log(requestOnly ? "Requested resolution" : "Resolved", { market_id: p.market_id }); await loadMarkets();
  }
  async function submitEvidence() { const m = selectedMarket(); if (!m) throw new Error("Select a market first"); await post(`/markets/${encodeURIComponent(m.market_id)}/evidence`, { oracle_id: $("#oracleId").value || "manual", title: $("#evidenceTitle").value, evidence_url: $("#evidenceUrl").value, statement: $("#disputeComment").value, source_type: "operator_note", submitter: "labs-ui", sandbox_short_mode: true }); log("Submitted evidence"); await loadMarkets(); }
  async function submitDisputeComment() { const m = selectedMarket(); if (!m) throw new Error("Select a market first"); await post(`/markets/${encodeURIComponent(m.market_id)}/evidence-dispute`, { commenter: $("#oracleId").value || "operator", comment: $("#disputeComment").value, sandbox_short_mode: true }); log("Submitted dispute"); await loadMarkets(); }
  async function loadPolymarket() {
    const box = $("#polymarketFeed"); box.textContent = "Loading read-only feed…";
    try {
      const payload = await api("/markets/external/polymarket?limit=8&active=true");
      if (!payload.ok) throw new Error(payload.error || "feed unavailable");
      box.textContent = (payload.markets || []).map((m) => `• ${m.question || m.slug} — ${(m.outcomes || []).map((o) => `${o.label} ${o.price || "-"}`).join(" / ")}`).join("\n") || "No public markets returned.";
      log("Loaded Polymarket feed", { count: (payload.markets || []).length });
    } catch (err) { box.textContent = `Could not load Polymarket feed: ${err.message}`; }
  }

  function wire() {
    $("#backToGrid").addEventListener("click", backToGrid);
    $("#searchInput").addEventListener("input", (e) => { state.query = e.target.value; renderGrid(); });
    $("#refreshMarkets").addEventListener("click", loadMarkets);
    $("#loadPolymarket").addEventListener("click", loadPolymarket);
    $("#seedMarket").addEventListener("click", () => createMarket({ question: "Will NetCoin complete the Markets Labs upgrade?", outcomes: ["YES", "NO"], oracle: "manual operator review", resolution_source: "NetCoin demo operator", legal_acknowledged: true, sandbox_short_mode: true }));
    $("#createMarketForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const cv = $("#closeTime").value; const close = cv ? Math.floor(new Date(cv).getTime() / 1000) : undefined;
      await createMarket({ question: $("#question").value, outcomes: $("#outcomes").value.split(",").map((x) => x.trim()).filter(Boolean), oracle: "manual", close_time: close, resolution_source: $("#resolutionSource").value, category: $("#marketCategory").value, tags: $("#marketTags").value, rules: $("#marketRules").value, legal_acknowledged: $("#legalAck").checked, sandbox_short_mode: true });
      e.target.reset(); $("#outcomes").value = "YES,NO"; $("#legalAck").checked = true;
    });
    $("#orderForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await placeOrder({ trader_address: $("#orderTrader").value, outcome_id: $("#orderOutcome").value, side: $("#orderSide").value, order_type: $("#orderType").value, time_in_force: $("#timeInForce").value, post_only: $("#postOnly").checked, quantity: Number($("#orderQuantity").value), price_bps: $("#orderType").value === "market" ? undefined : Number($("#orderPrice").value), allow_unverified_demo: true, sandbox_short_mode: true });
      } catch (err) { alert(`Order failed: ${err.message}`); }
    });
    $("#requestResolution").addEventListener("click", () => resolveMarket(true).catch((e) => alert(e.message)));
    $("#submitEvidence").addEventListener("click", () => submitEvidence().catch((e) => alert(e.message)));
    $("#submitDispute").addEventListener("click", () => submitDisputeComment().catch((e) => alert(e.message)));
    $("#resolveForm").addEventListener("submit", (e) => { e.preventDefault(); resolveMarket(false).catch((err) => alert(err.message)); });
  }

  wire();
  loadMarkets();
})();
