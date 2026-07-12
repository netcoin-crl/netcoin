'use strict';

const $ = (s) => document.querySelector(s);
const esc = (value) => String(value ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const asNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

function formatDuration(seconds) {
  const n = asNumber(seconds);
  if (n === null || n < 0) return '—';
  const days = Math.floor(n / 86400);
  const hours = Math.floor((n % 86400) / 3600);
  const minutes = Math.floor((n % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  return `${Math.max(0, minutes)}m`;
}

async function getJson(path) {
  const r = await fetch(path, { cache: 'no-store' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

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

function renderNetworkSnapshot({ health, latest, mempool, peers, errors }) {
  const height = asNumber(health?.height) ?? asNumber(latest?.height) ?? asNumber(latest?.blocks?.[0]?.height);
  const tip = health?.tip_hash || latest?.tip_hash || latest?.blocks?.[0]?.hash || 'unavailable';
  const mempoolDepth = asNumber(health?.mempool) ?? asNumber(health?.mempool_transactions) ?? asNumber(mempool?.size) ?? asNumber(mempool?.count) ?? asNumber(mempool?.transactions?.length);
  const mempoolBytes = asNumber(mempool?.bytes) ?? asNumber(mempool?.vbytes);
  const peerCount = asNumber(health?.peers) ?? asNumber(peers?.count) ?? asNumber(peers?.peers?.length);
  const uptime = asNumber(health?.uptime_seconds) ?? asNumber(health?.uptime);
  const ok = Boolean(health?.ok) || height !== null;

  $('#networkDot').className = `dot ${ok ? 'ok' : 'err'}`;
  $('#networkState').textContent = ok ? 'Node reachable' : 'Node unavailable';
  $('#networkUpdated').textContent = ok ? `Updated ${new Date().toLocaleTimeString()}` : `Unable to read live metrics${errors.length ? ': ' + errors.join('; ') : ''}`;
  $('#statusHeight').textContent = height === null ? '—' : height.toLocaleString();
  $('#statusTip').textContent = tip === 'unavailable' ? 'tip unavailable' : `tip ${String(tip).slice(0, 18)}…`;
  $('#statusMempool').textContent = mempoolDepth === null ? '—' : mempoolDepth.toLocaleString();
  $('#statusMempoolBytes').textContent = mempoolBytes === null ? 'transactions queued' : `${mempoolBytes.toLocaleString()} virtual bytes`;
  $('#statusPeers').textContent = peerCount === null ? '—' : peerCount.toLocaleString();
  $('#statusPeerDetail').textContent = peerCount === null ? 'known peers unavailable' : 'known peers';
  $('#statusUptime').textContent = formatDuration(uptime);
  $('#statusHealthDetail').textContent = health?.version ? `node ${health.version}` : (ok ? 'health endpoint online' : 'health endpoint unavailable');
}

async function loadNetworkSnapshot() {
  const targets = [
    ['health', '/api/health'],
    ['latest', '/api/latest?n=1'],
    ['mempool', '/api/mempool?transactions=0'],
    ['peers', '/api/peers'],
  ];
  const settled = await Promise.all(targets.map(async ([name, path]) => [name, await getJson(path)]).map((p) => p.catch((e) => e)));
  const data = { health: null, latest: null, mempool: null, peers: null, errors: [] };
  settled.forEach((item, idx) => {
    const name = targets[idx][0];
    if (item instanceof Error) {
      data.errors.push(`${name}: ${item.message}`);
    } else {
      data[item[0]] = item[1];
    }
  });
  renderNetworkSnapshot(data);
}

(async () => {
  await Promise.allSettled([
    loadNetworkSnapshot(),
    Promise.all([
      serviceOk('API latest', '/api/latest?n=1'),
      serviceOk('API health', '/api/health'),
      serviceOk('Faucet', '/faucet/status'),
      serviceOk('Explorer data', '/api/info'),
    ]).then(renderServices),
  ]);
  try {
    const r = await fetch('professional-readiness.json', { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    renderReadiness(await r.json());
  } catch (e) {
    $('#readinessSummary').textContent = 'Professional checklist could not be loaded: ' + e.message;
    $('#readinessGrid').innerHTML = '<p class="err">Readiness data unavailable.</p>';
  }
})();
