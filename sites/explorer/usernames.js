'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const shortAddr = (v) => { const s = String(v || ''); return s.length > 22 ? `${s.slice(0, 10)}…${s.slice(-6)}` : s; };
  const fmtTime = (t) => { const n = Number(t || 0); if (!n) return ''; try { return new Date(n * 1000).toLocaleString(); } catch { return ''; } };

  async function api(path) {
    const r = await fetch('/api' + path);
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = { raw: t }; }
    if (!r.ok) throw new Error(d.error || 'HTTP ' + r.status);
    return d;
  }

  let all = [];

  function card(rec) {
    return `<article class="card" style="padding:12px 14px;margin-bottom:8px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><a href="https://community.netcoin.online/u/${encodeURIComponent(rec.username)}" style="font-weight:800">@${esc(rec.username)}</a><span class="muted mono">${esc(shortAddr(rec.address))}</span></div><div class="muted" style="font-size:12px;margin-top:4px">Claimed ${esc(fmtTime(rec.claimed_at))} at height ${esc(rec.height)} &middot; <a href="tx.html?txid=${encodeURIComponent(rec.txid)}">${esc(shortAddr(rec.txid))}</a></div></article>`;
  }

  function render() {
    const q = ($('#usernameSearchInput').value || '').trim().toLowerCase();
    const filtered = q ? all.filter((r) => r.username.includes(q) || (r.address || '').toLowerCase().includes(q)) : all;
    $('#usernameCount').textContent = `${filtered.length} of ${all.length} on-chain usernames`;
    $('#usernameList').innerHTML = filtered.length
      ? filtered.map(card).join('')
      : '<div class="empty-state">No on-chain usernames match.</div>';
  }

  async function load() {
    $('#usernameList').innerHTML = 'Loading…';
    try {
      const d = await api('/usernames/onchain');
      all = (d.usernames || []).sort((a, b) => (a.height || 0) - (b.height || 0));
      render();
    } catch (e) {
      $('#usernameList').innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    }
  }

  $('#usernameSearchForm').addEventListener('submit', (e) => { e.preventDefault(); render(); });
  $('#usernameSearchInput').addEventListener('input', render);
  load();
})();
