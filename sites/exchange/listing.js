'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  async function get(path) {
    const res = await fetch('/api' + path);
    const text = await res.text();
    let data = {};
    try { data = JSON.parse(text); } catch { data = { error: 'non-JSON response from node' }; }
    if (!res.ok || data.error) throw new Error(data.error || 'HTTP ' + res.status);
    return data;
  }
  function gate(g) {
    const cls = g.status === 'available' ? 'ok' : g.status === 'external' ? 'warn' : 'warn';
    return '<div class="check"><span>' + esc(g.label) + '<small>' + esc(g.evidence || g.id || '') + '</small></span><b class="' + cls + '">' + esc(g.status) + '</b></div>';
  }
  function command(label, value) {
    return '<div class="listing-command"><span>' + esc(label) + '</span><code>' + esc(value) + '</code><button type="button" data-copy-command="' + esc(value) + '">Copy</button></div>';
  }
  function counts(payload) {
    const c = payload.live_counts || {};
    return Object.entries(c).map(([k, v]) => '<div class="check"><span>' + esc(k.replaceAll('_', ' ')) + '</span><b>' + esc(v) + '</b></div>').join('') || '<p class="muted">No live exchange state yet.</p>';
  }
  function render(payload) {
    $('#codeGates').innerHTML = (payload.code_gates || []).map(gate).join('');
    $('#externalBlockers').innerHTML = (payload.external_blockers || []).map(gate).join('');
    $('#liveCounts').innerHTML = counts(payload);
    $('#listingCommands').innerHTML = Object.entries(payload.commands || {}).map(([k, v]) => command(k.replaceAll('_', ' '), v)).join('') || '<p class="muted">No commands published.</p>';
    document.querySelectorAll('[data-copy-command]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        await navigator.clipboard?.writeText(btn.getAttribute('data-copy-command') || '');
        btn.textContent = 'Copied';
        setTimeout(() => { btn.textContent = 'Copy'; }, 900);
      });
    });
  }
  async function boot() {
    try { render(await get('/exchange/listing-readiness')); }
    catch (e) {
      $('#codeGates').innerHTML = '<p class="muted">Listing readiness API unavailable: ' + esc(e.message) + '</p>';
      $('#externalBlockers').innerHTML = '<p class="muted">External blockers still apply even when the API is offline.</p>';
    }
  }
  boot();
})();
