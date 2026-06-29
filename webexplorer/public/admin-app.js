"use strict";
(function () {
  const API = (location.origin + "/api").replace(/\/$/, "");
  const TOKEN_KEY = "netcoin.admin.token";
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>\"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (n) => Number(n || 0).toLocaleString();
  const short = (s, n = 16) => String(s || "").length > n ? String(s).slice(0, n) + "…" : String(s || "");
  const tokenInput = $("#adminToken");
  tokenInput.value = localStorage.getItem(TOKEN_KEY) || "";

  function setMsg(text, cls = "muted") { const m = $("#msg"); m.className = cls; m.textContent = text; }
  function headers(extra) {
    const h = { ...(extra || {}) };
    const token = tokenInput.value.trim();
    if (token) h["X-Netcoin-Admin-Token"] = token;
    return h;
  }
  async function api(path) {
    const r = await fetch(API + path, { headers: headers() });
    const txt = await r.text(); let d; try { d = JSON.parse(txt); } catch { d = { error: txt }; }
    if (!r.ok || d.error) throw new Error(d.error || ("HTTP " + r.status));
    return d;
  }
  async function post(path, body) {
    const r = await fetch(API + path, { method: "POST", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body || {}) });
    const txt = await r.text(); let d; try { d = JSON.parse(txt); } catch { d = { error: txt }; }
    if (!r.ok || d.error) throw new Error(d.error || ("HTTP " + r.status));
    return d;
  }
  function renderSummary(s) {
    const c = s.counts || {}, sec = s.security || {}, node = s.node || {};
    $("#summary").innerHTML = `<div class="card"><h2>Operations summary</h2><div class="grid">
      <div class="stat"><div class="k">Height</div><div class="v">${fmt(node.height)}</div><div class="muted mono">${esc(short(node.tip_hash, 24))}</div></div>
      <div class="stat"><div class="k">Invoices</div><div class="v">${fmt(c.invoices)}</div><div class="muted">${esc(JSON.stringify(c.invoice_statuses || {}))}</div></div>
      <div class="stat"><div class="k">Payout plans</div><div class="v">${fmt(c.payout_plans)}</div><div class="muted">${esc(JSON.stringify(c.payout_statuses || {}))}</div></div>
      <div class="stat"><div class="k">Webhooks</div><div class="v">${fmt(c.webhooks)}</div><div class="muted">dead letters ${fmt(c.webhook_dead_letters)}</div></div>
      <div class="stat"><div class="k">Storage</div><div class="v">${esc(sec.storage_backend || "?")}</div><div class="muted mono">${esc(short(sec.storage_path, 36))}</div></div>
      <div class="stat"><div class="k">Admin token</div><div class="v">${sec.admin_token_required ? "on" : "off"}</div><div class="muted">protect before public deploy</div></div>
    </div></div>`;
  }
  function statusClass(status) {
    if (status === "broadcast_recorded") return "ok";
    if (status === "rejected") return "err";
    if (status === "pending_operator_review") return "warn";
    return "muted";
  }
  function renderPayouts(data) {
    const rows = data.payout_plans || [];
    if (!rows.length) { $("#payouts").innerHTML = "<p class='muted'>No payout plans yet.</p>"; return; }
    const html = rows.map((p) => `<tr>
      <td><div class="mono">${esc(p.payout_id)}</div><span class="badge">${esc(p.kind)}</span> <span class="badge">${esc(p.source_type)}</span></td>
      <td><span class="${statusClass(p.status)}">${esc(p.status)}</span><br><span class="muted">${esc(p.memo || "")}</span></td>
      <td>${esc(p.total)} NET<br><span class="muted">${fmt(p.outputs?.length || 0)} outputs</span></td>
      <td class="row">
        <button class="secondary" data-act="bundle" data-id="${esc(p.payout_id)}">Export bundle</button>
        <button data-act="approve" data-id="${esc(p.payout_id)}">Approve</button>
        <button class="secondary" data-act="signed" data-id="${esc(p.payout_id)}">Record signed</button>
        <button class="secondary" data-act="broadcast" data-id="${esc(p.payout_id)}">Record txid</button>
        <button class="danger" data-act="reject" data-id="${esc(p.payout_id)}">Reject</button>
      </td>
    </tr>`).join("");
    $("#payouts").innerHTML = `<table><thead><tr><th>Plan</th><th>Status</th><th>Total</th><th>Actions</th></tr></thead><tbody>${html}</tbody></table>`;
  }
  async function loadAll() {
    try {
      const [summary, payouts] = await Promise.all([api("/admin/summary"), api("/admin/payouts")]);
      renderSummary(summary); renderPayouts(payouts); setMsg("Loaded admin dashboard.", "ok");
    } catch (e) { setMsg(e.message, "err"); }
  }
  async function handlePayoutClick(e) {
    const btn = e.target.closest("button[data-act]"); if (!btn) return;
    const id = btn.dataset.id, act = btn.dataset.act;
    try {
      if (act === "bundle") {
        const b = await api(`/admin/payouts/${encodeURIComponent(id)}/bundle`);
        $("#bundleBox").textContent = JSON.stringify(b, null, 2);
      } else if (act === "approve") {
        const reviewer = prompt("Reviewer/operator name", "operator") || "operator";
        await post(`/admin/payouts/${encodeURIComponent(id)}/review`, { approved: true, reviewer, notes: "Approved from admin dashboard" });
        await loadAll();
      } else if (act === "reject") {
        const notes = prompt("Reason for rejection", "Rejected by operator") || "Rejected";
        await post(`/admin/payouts/${encodeURIComponent(id)}/reject`, { notes });
        await loadAll();
      } else if (act === "signed") {
        const txid = prompt("Signed txid or signing reference", "") || "";
        const raw = prompt("Optional signed raw tx preview/artifact", "") || "";
        await post(`/admin/payouts/${encodeURIComponent(id)}/signed`, { txid, signed_tx: raw, signer: "operator" });
        await loadAll();
      } else if (act === "broadcast") {
        const txid = prompt("Broadcast txid", ""); if (!txid) return;
        await post(`/admin/payouts/${encodeURIComponent(id)}/broadcasted`, { txid, operator: "operator" });
        await loadAll();
      }
    } catch (err) { setMsg(err.message, "err"); }
  }
  async function deliverHooks() {
    try { const r = await post("/merchant/webhook-events/deliver", { max_events: 20 }); $("#auditBox").textContent = JSON.stringify(r, null, 2); await loadAll(); }
    catch (e) { setMsg(e.message, "err"); }
  }
  async function loadAudit() {
    try { const [audit, sec] = await Promise.all([api("/security/audit"), api("/security/status")]); $("#auditBox").textContent = JSON.stringify({ security: sec, audit }, null, 2); }
    catch (e) { setMsg(e.message, "err"); }
  }
  $("#saveToken").onclick = () => { localStorage.setItem(TOKEN_KEY, tokenInput.value.trim()); setMsg("Saved token in this browser.", "ok"); loadAll(); };
  $("#clearToken").onclick = () => { localStorage.removeItem(TOKEN_KEY); tokenInput.value = ""; setMsg("Cleared local token.", "warn"); };
  $("#refresh").onclick = loadAll;
  $("#deliverHooks").onclick = deliverHooks;
  $("#loadAudit").onclick = loadAudit;
  $("#payouts").addEventListener("click", handlePayoutClick);
  loadAll();
})();
