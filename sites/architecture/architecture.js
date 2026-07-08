(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  async function loadArchitecture() {
    try {
      const res = await fetch('/api/architecture');
      if (!res.ok) throw new Error('status ' + res.status);
      return await res.json();
    } catch (err) {
      return {
        codename: 'Professional Architecture Space',
        final_version_target: 'v1.0 production-candidate',
        principle: 'Rust core + TypeScript app + Python ops/reference',
        layers: [
          { id: 'core-rs', language: 'Rust', owns: ['consensus', 'mempool', 'wallet-core'], status: 'upgrade space added', migration_rule: 'Prove parity before replacing live paths.' },
          { id: 'api/web', language: 'TypeScript', owns: ['API', 'web app', 'dashboards'], status: 'upgrade space added', migration_rule: 'OpenAPI and browser E2E must pass.' },
          { id: 'ops/python', language: 'Python', owns: ['reference implementation', 'tests', 'release tooling'], status: 'active', migration_rule: 'Remain the reference/ops layer.' }
        ],
        upgrade_lanes: ['core parity vectors', 'Rust consensus MVP', 'Next.js web migration', 'v1.0 production candidate'],
        final_version_gates: [{ gate: 'Full test suite green' }, { gate: 'External crypto/security audit completed' }]
      };
    }
  }

  function render(data) {
    $('archStatus').textContent = data.codename || 'Architecture ready';
    $('archTarget').textContent = data.final_version_target || 'v1.0 production-candidate';
    $('archLayers').innerHTML = (data.layers || []).map((layer) => `
      <article class="arch-card">
        <h3>${esc(layer.id)}</h3>
        <span class="lang">${esc(layer.language)}</span>
        <p>${esc(layer.status || '')}</p>
        <ul>${(layer.owns || []).slice(0, 6).map((item) => `<li>${esc(item)}</li>`).join('')}</ul>
        <p><strong>Migration:</strong> ${esc(layer.migration_rule || '')}</p>
      </article>`).join('');
    const migration = data.migration?.status || {};
    const lanes = migration.lanes || [];
    const parity = data.migration?.parity || {};
    const fingerprint = migration.vector_fingerprint ? migration.vector_fingerprint.slice(0, 16) : 'pending';
    if ($('migrationStatus')) {
      $('migrationStatus').innerHTML = `
        <div class="metric-row"><span>Live runtime</span><strong>${esc(migration.current_live_runtime || 'python-reference-app')}</strong></div>
        <div class="metric-row"><span>Target runtime</span><strong>${esc(migration.target_runtime || 'rust-core-typescript-app')}</strong></div>
        <div class="metric-row"><span>Parity lanes</span><strong>${lanes.length}</strong></div>
        <div class="metric-row"><span>Vector fingerprint</span><code>${esc(fingerprint)}</code></div>
        <div class="metric-row"><span>Executable parity</span><strong>${parity.ok ? 'green' : 'pending'}</strong></div>
        <div class="metric-row"><span>Parity checks</span><strong>${esc(parity.passed || 0)} / ${esc(parity.total || 0)}</strong></div>
        <div class="metric-row"><span>Rust/TS expansion</span><strong>${data.migration?.expansion?.ok ? 'ready' : 'pending'}</strong></div>
        <div class="lane-list">${lanes.map((lane) => `<span>${esc(lane.id)} · ${esc(lane.promotion_status || lane.status || '')}</span>`).join('')}</div>
      `;
    }
    $('upgradeLanes').innerHTML = (data.upgrade_lanes || []).map((lane) => `<span>${esc(lane)}</span>`).join('');
    $('finalGates').innerHTML = (data.final_version_gates || []).map((item) => `<div>${esc(item.gate || item)}</div>`).join('');
  }

  loadArchitecture().then(render);
})();
