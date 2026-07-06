"use strict";

(() => {
  const $ = (sel) => document.querySelector(sel);
  const state = { markets: [], selectedId: "", apiOk: false };
  const apiBase = localStorage.getItem("netcoinApiBase") || "/api";

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  function fmtTime(ts) {
    if (!ts) return "n/a";
    const num = Number(ts);
    if (!Number.isFinite(num)) return esc(ts);
    return new Date(num * 1000).toLocaleString();
  }

  function log(msg, payload) {
    const box = $("#activityLog");
    const line = `[${new Date().toLocaleTimeString()}] ${msg}`;
    const extra = payload ? `\n${JSON.stringify(payload, null, 2)}` : "";
    box.textContent = `${line}${extra}\n\n${box.textContent}`.slice(0, 9000);
  }

  async function api(path, options = {}) {
    const res = await fetch(`${apiBase}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options
    });
    const text = await res.text();
    let payload;
    try { payload = text ? JSON.parse(text) : {}; } catch (_) { payload = { raw: text }; }
    if (!res.ok || payload.ok === false) {
      throw new Error(payload.error || `HTTP ${res.status}`);
    }
    return payload;
  }

  function post(path, body) {
    return api(path, { method: "POST", body: JSON.stringify(body || {}) });
  }

  function selectedMarket() {
    return state.markets.find((m) => m.market_id === state.selectedId) || state.markets[0] || null;
  }

  function marketBadge(m) {
    const cls = m.status === "open" ? "ok" : m.status === "resolved" ? "" : "err";
    return `<span class="pill"><span class="dot ${cls}"></span>${esc(m.status || "unknown")}</span>`;
  }

  function renderStats(totals) {
    const stats = totals || {};
    $("#marketStats").innerHTML = [
      ["Markets", stats.count ?? state.markets.length],
      ["Open", stats.open ?? state.markets.filter((m) => m.status === "open").length],
      ["Closed", stats.closed ?? state.markets.filter((m) => m.status === "closed").length],
      ["Resolved", stats.resolved ?? state.markets.filter((m) => m.status === "resolved").length],
      ["Volume", stats.volume || "0"]
    ].map(([k, v]) => `<div class="stat"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("");
  }

  function renderMarketList() {
    const list = $("#marketList");
    if (!state.markets.length) {
      list.innerHTML = `<p class="muted">No markets yet. Create a sample or connect to a running NetCoin API.</p>`;
      return;
    }
    list.innerHTML = state.markets.map((m) => {
      const stats = m.stats || {};
      const active = m.market_id === state.selectedId ? " active" : "";
      const outcomes = (m.outcomes || []).map((o) => `<span class="pill">${esc(o.label)} ${esc(((stats.implied_probabilities || {})[o.outcome_id] || {}).probability || "-")}</span>`).join(" ");
      return `<button class="market-card${active}" type="button" data-market-id="${esc(m.market_id)}">
        <span>${marketBadge(m)}</span>
        <b>${esc(m.question)}</b>
        <small class="mono">${esc(m.market_id)}</small>
        <span class="market-outcomes">${outcomes}</span>
        <span class="muted">Trades: ${esc(stats.trade_count || 0)} · Volume: ${esc(stats.volume || "0")} · Closes: ${fmtTime(m.close_time)}</span>
      </button>`;
    }).join("");
    list.querySelectorAll("[data-market-id]").forEach((btn) => btn.addEventListener("click", () => {
      state.selectedId = btn.getAttribute("data-market-id") || "";
      renderAll();
    }));
  }

  function renderOutcomeSelectors(m) {
    const options = (m?.outcomes || []).map((o) => `<option value="${esc(o.outcome_id)}">${esc(o.label)} (${esc(o.outcome_id)})</option>`).join("");
    $("#orderOutcome").innerHTML = options || `<option value="">Select market</option>`;
    $("#resolveOutcome").innerHTML = options || `<option value="">Select market</option>`;
  }

  function renderSparkline(m) {
    const points = (((m.analytics || {}).price_points) || []).slice(-40);
    if (!points.length) return `<p class="muted">No trades yet. The probability chart appears after the first fill.</p>`;
    const w = 360, h = 110, pad = 8;
    const coords = points.map((p, i) => {
      const x = pad + (i * (w - 2 * pad) / Math.max(1, points.length - 1));
      const y = h - pad - ((Number(p.price_bps || 0) / 10000) * (h - 2 * pad));
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<svg class="sparkline" viewBox="0 0 ${w} ${h}" role="img" aria-label="Recent price chart"><polyline points="${coords}" fill="none" stroke="currentColor" stroke-width="3"/><line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="currentColor" opacity=".2"/><line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h-pad}" stroke="currentColor" opacity=".2"/></svg>`;
  }

  function renderOrderbook(m) {
    if (!m) return "";
    return (m.outcomes || []).map((outcome) => {
      const book = (m.orderbook || {})[outcome.outcome_id] || { buys: [], sells: [] };
      const maxRows = Math.max(book.buys.length, book.sells.length, 1);
      const rows = Array.from({ length: maxRows }, (_, i) => {
        const bid = book.buys[i];
        const ask = book.sells[i];
        return `<tr>
          <td>${bid ? `${esc(bid.price)} / ${esc(bid.remaining)}<br><button class="mini secondary" data-cancel="${esc(bid.order_id)}">Cancel</button>` : ""}</td>
          <td>${ask ? `${esc(ask.price)} / ${esc(ask.remaining)}<br><button class="mini secondary" data-cancel="${esc(ask.order_id)}">Cancel</button>` : ""}</td>
        </tr>`;
      }).join("");
      return `<div class="book"><h3>${esc(outcome.label)} <span class="muted mono">${esc(outcome.outcome_id)}</span></h3><p class="muted">Best bid ${esc(book.best_bid || "-")} · Best ask ${esc(book.best_ask || "-")} · Spread ${esc(book.spread || "-")}</p><table><thead><tr><th>Bid price / shares</th><th>Ask price / shares</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }).join("");
  }

  function renderTrades(m) {
    const trades = (m?.trades || []).slice(-12).reverse();
    if (!trades.length) return `<p class="muted">No trades yet.</p>`;
    return `<table><thead><tr><th>Time</th><th>Outcome</th><th>Price</th><th>Qty</th><th>Maker/Taker</th></tr></thead><tbody>${trades.map((t) => `<tr><td>${fmtTime(t.created_at)}</td><td>${esc(t.outcome_id)}</td><td>${esc(t.price || (Number(t.price_bps || 0) / 10000).toFixed(4))}</td><td>${esc(t.quantity)}</td><td class="mono">${esc(t.maker || "")}<br>${esc(t.taker || "")}</td></tr>`).join("")}</tbody></table>`;
  }

  function renderWallets(m) {
    const entries = Object.values(m?.wallets || {}).slice(0, 10);
    if (!entries.length) return `<p class="muted">Demo wallets appear after orders are placed.</p>`;
    return `<table><thead><tr><th>Trader</th><th>Balance</th><th>Reserved</th><th>Positions</th></tr></thead><tbody>${entries.map((w) => {
      const pos = Object.entries((m.positions || {})[w.trader_id] || {}).map(([k, v]) => `${k}:${v}`).join(" ") || "-";
      return `<tr><td class="mono">${esc(w.trader_id)}</td><td>${esc(w.balance || "0")}</td><td>${esc(w.reserved || "0")}</td><td>${esc(pos)}</td></tr>`;
    }).join("")}</tbody></table>`;
  }

  function renderDetail() {
    const m = selectedMarket();
    renderOutcomeSelectors(m);
    const detail = $("#marketDetail");
    if (!m) {
      $("#selectedMarketStatus").textContent = "none selected";
      detail.classList.add("empty");
      detail.innerHTML = "Select or create a market to see the order book.";
      return;
    }
    state.selectedId = m.market_id;
    $("#selectedMarketStatus").innerHTML = marketBadge(m);
    detail.classList.remove("empty");
    const stats = m.stats || {};
    const workflow = m.resolution_workflow || {};
    detail.innerHTML = `<div class="detail-title"><div><h2>${esc(m.question)}</h2><p class="mono muted">${esc(m.market_id)}</p></div>${marketBadge(m)}</div>
      <p class="notice warn">${esc(m.warning || "Testnet/play-money only.")}</p>
      <div class="stats compact-stats"><div class="stat"><div class="k">Volume</div><div class="v">${esc(stats.volume || "0")}</div></div><div class="stat"><div class="k">Open interest</div><div class="v">${esc(stats.open_interest_shares || 0)}</div></div><div class="stat"><div class="k">Liquidity</div><div class="v">${esc(stats.liquidity_shares || 0)}</div></div><div class="stat"><div class="k">Trades</div><div class="v">${esc(stats.trade_count || 0)}</div></div></div>
      <h3>Probability chart</h3>${renderSparkline(m)}
      <h3>Order book</h3>${renderOrderbook(m)}
      <h3>Recent trades</h3>${renderTrades(m)}
      <h3>Demo wallets & positions</h3>${renderWallets(m)}
      <h3>Resolution</h3><p class="muted">Workflow: ${esc(workflow.status || "unresolved")} · Source: ${esc(m.resolution_source || workflow.evidence_url || "manual")}</p>`;
    detail.querySelectorAll("[data-cancel]").forEach((btn) => btn.addEventListener("click", async () => {
      await cancelOrder(btn.getAttribute("data-cancel") || "");
    }));
  }

  function renderAll(totals) {
    renderStats(totals);
    renderMarketList();
    renderDetail();
  }

  async function loadMarkets() {
    try {
      const payload = await api("/markets");
      state.markets = payload.markets || [];
      if (!state.selectedId && state.markets[0]) state.selectedId = state.markets[0].market_id;
      state.apiOk = true;
      $("#apiStatus").textContent = `Connected to ${apiBase}. ${payload.warning || ""}`;
      renderAll(payload.totals);
    } catch (err) {
      state.apiOk = false;
      $("#apiStatus").textContent = `API unavailable: ${err.message}`;
      renderStats({ count: 0, open: 0, closed: 0, resolved: 0, volume: "0" });
      $("#marketList").innerHTML = `<p class="muted">Could not load markets from ${esc(apiBase)}. Run a NetCoin node/explorer server, then refresh.</p>`;
      log("Market load failed", { error: err.message });
    }
  }

  async function createMarket(body) {
    const payload = await post("/markets", body);
    log("Created market", { market_id: payload.market_id });
    state.selectedId = payload.market_id;
    await loadMarkets();
  }

  async function placeOrder(body) {
    const m = selectedMarket();
    if (!m) throw new Error("Select a market first");
    const payload = await post(`/markets/${encodeURIComponent(m.market_id)}/order`, body);
    log("Placed order", { market_id: payload.market_id, trades: (payload.trades || []).length });
    await loadMarkets();
  }

  async function cancelOrder(orderId) {
    const m = selectedMarket();
    if (!m || !orderId) return;
    const payload = await post(`/markets/${encodeURIComponent(m.market_id)}/orders/${encodeURIComponent(orderId)}/cancel`, { operator_override: true });
    log("Canceled order", { market_id: payload.market_id, order_id: orderId });
    await loadMarkets();
  }

  async function resolveMarket(requestOnly) {
    const m = selectedMarket();
    if (!m) throw new Error("Select a market first");
    const body = {
      winning_outcome_id: $("#resolveOutcome").value,
      evidence_url: $("#evidenceUrl").value,
      resolution_note: $("#evidenceUrl").value,
      payout_per_share: m.unit_payout || "1",
      operator_approved: !requestOnly
    };
    const path = requestOnly ? `/markets/${encodeURIComponent(m.market_id)}/resolution-request` : `/markets/${encodeURIComponent(m.market_id)}/resolve`;
    const payload = await post(path, body);
    log(requestOnly ? "Requested resolution" : "Resolved market", { market_id: payload.market_id, winning_outcome_id: payload.winning_outcome_id });
    await loadMarkets();
  }

  async function loadPolymarket() {
    const box = $("#polymarketFeed");
    box.textContent = "Loading read-only public feed...";
    try {
      const payload = await api("/markets/external/polymarket?limit=8&active=true");
      if (!payload.ok) throw new Error(payload.error || "feed unavailable");
      const rows = (payload.markets || []).map((m) => `<div class="external-market"><b>${esc(m.question || m.slug || m.external_id)}</b><span class="muted">Volume: ${esc(m.volume || "-")} · Liquidity: ${esc(m.liquidity || "-")} · End: ${esc(m.end_date || "-")}</span><span class="mono muted">${esc(m.external_id || "")}</span></div>`).join("");
      box.innerHTML = rows || `<p class="muted">No public markets returned.</p>`;
      log("Loaded Polymarket read-only feed", { count: (payload.markets || []).length });
    } catch (err) {
      box.innerHTML = `<p class="muted">Could not load Polymarket feed through the NetCoin backend: ${esc(err.message)}</p>`;
      log("Polymarket bridge failed", { error: err.message });
    }
  }

  function wireForms() {
    $("#refreshMarkets").addEventListener("click", loadMarkets);
    $("#loadPolymarket").addEventListener("click", loadPolymarket);
    $("#seedMarket").addEventListener("click", async () => {
      await createMarket({
        question: "Will NetCoin complete the Markets Labs upgrade?",
        outcomes: ["YES", "NO"],
        oracle: "manual operator review",
        resolution_source: "NetCoin demo operator",
        legal_acknowledged: true,
        sandbox_short_mode: true
      });
    });
    $("#createMarketForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const closeValue = $("#closeTime").value;
      const close = closeValue ? Math.floor(new Date(closeValue).getTime() / 1000) : undefined;
      await createMarket({
        question: $("#question").value,
        outcomes: $("#outcomes").value.split(",").map((x) => x.trim()).filter(Boolean),
        oracle: "manual",
        close_time: close,
        resolution_source: $("#resolutionSource").value,
        legal_acknowledged: $("#legalAck").checked,
        sandbox_short_mode: true
      });
      event.target.reset();
      $("#outcomes").value = "YES,NO";
      $("#legalAck").checked = true;
    });
    $("#orderForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await placeOrder({
        trader_address: $("#orderTrader").value,
        outcome_id: $("#orderOutcome").value,
        side: $("#orderSide").value,
        quantity: Number($("#orderQuantity").value),
        price_bps: Number($("#orderPrice").value),
        allow_unverified_demo: true,
        sandbox_short_mode: true
      });
    });
    $("#requestResolution").addEventListener("click", async () => resolveMarket(true));
    $("#resolveForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await resolveMarket(false);
    });
  }

  wireForms();
  loadMarkets();
})();
