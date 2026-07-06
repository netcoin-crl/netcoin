'use strict';

const $ = (s) => document.querySelector(s);
const esc = (value) => String(value ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function serviceOk(label, path) {
  const started = performance.now();
  try {
    const r = await fetch(path, { cache: 'no-store' });
    return { label, ok: r.ok, detail: r.ok ? `${Math.round(performance.now() - started)} ms` : `HTTP ${r.status}` };
  } catch (e) {
    return { label, ok: false, detail: e.message || 'offline' };
  }
}

function renderServices(items) {
  const el = $('#serviceChecks');
  if (!el) return;
  el.innerHTML = items.map((item) => `
    <div class="stat">
      <div class="k">${esc(item.label)}</div>
      <div class="v ${item.ok ? 'ok' : 'err'}"><span class="dot ${item.ok ? 'ok' : 'err'}"></span> ${item.ok ? 'Online' : 'Issue'}</div>
      <div class="muted">${esc(item.detail)}</div>
    </div>
  `).join('');
}

function renderReadiness(data) {
  const summary = $('#readinessSummary');
  const grid = $('#readinessGrid');
  if (!summary || !grid) return;
  const counts = data.categories.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
  summary.textContent = `${data.categories.length} categories tracked · ${counts.done || 0} done · ${counts['in progress'] || 0} in progress · ${counts.next || 0} next priorities. Updated ${data.updated}.`;
  grid.innerHTML = data.categories.map((item) => `
    <div class="card">
      <h2>${esc(item.name)}</h2>
      <p><span class="pill">${esc(item.status)}</span></p>
      <p class="muted"><strong>Done:</strong> ${esc((item.done || []).join(', ') || 'none yet')}</p>
      <p class="muted"><strong>Next:</strong> ${esc((item.next || []).join(', ') || 'none listed')}</p>
    </div>
  `).join('');
}

(async () => {
  renderServices(await Promise.all([
    serviceOk('API latest', '/api/latest?n=1'),
    serviceOk('API health', '/api/health'),
    serviceOk('Faucet', '/faucet/status'),
    serviceOk('Explorer data', '/api/info'),
  ]));
  try {
    const r = await fetch('professional-readiness.json', { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    renderReadiness(await r.json());
  } catch (e) {
    $('#readinessSummary').textContent = 'Professional checklist could not be loaded: ' + e.message;
    $('#readinessGrid').innerHTML = '<p class="err">Readiness data unavailable.</p>';
  }
})();
