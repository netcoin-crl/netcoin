'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function get(path) { const r = await fetch('/api' + path); const text = await r.text(); let data; let parsed = true; try { data = JSON.parse(text); } catch { parsed = false; data = {}; } if (!r.ok || data.error) throw new Error(parsed ? (data.error || 'HTTP ' + r.status) : 'HTTP ' + r.status + ' (non-JSON response)'); return data; }
  function pill(status) { return '<span class="pill ' + esc(status || 'partial') + '">' + esc(status || 'partial') + '</span>'; }
  function kv(k, v) { return '<div class="kv"><span>' + esc(k) + '</span><b>' + esc(v) + '</b></div>'; }
  function runbook(alert){ const key=String(alert.alert||alert.message||'').toLowerCase(); if(key.includes('peer')) return 'Check peerdb, rotate outbound slots, confirm seed reachability.'; if(key.includes('mempool')) return 'Inspect fee floor, spam score, and recent replacements.'; if(key.includes('chain')||key.includes('height')) return 'Compare checkpoints, block time, and public seed tips.'; return 'Open ops bundle, collect logs, and acknowledge incident.'; }
  function render(data, live) {
    $('#summaryCards').innerHTML = [
      ['Product status', data.status, pill(data.status)], ['Height', live.height ?? '—', 'node tip'], ['Peers', (live.peers||[]).length, 'connected/known'], ['Mempool', live.mempool?.count ?? live.mempool?.transactions ?? 0, 'txs'], ['Alerts', data.alerts?.length || 0, (data.alerts?.length ? 'needs review' : 'clear')], ['Fingerprint', String(data.fingerprint || '').slice(0,12), 'health hash']
    ].map(([label, value, note]) => '<div class="stat"><span>' + esc(label) + '</span><b>' + value + '</b><small>' + note + '</small></div>').join('');
    $('#alerts').innerHTML = data.alerts?.length ? data.alerts.map((a) => '<div class="mini">' + pill(a.severity || 'warning') + ' <b>' + esc(a.alert) + '</b><p>' + esc(a.message) + '</p><small>' + esc(runbook(a)) + '</small></div>').join('') : '<p class="muted">No active alerts from the current health-center payload.</p>';
    const metrics = data.metrics || {}; $('#metrics').innerHTML = Object.keys(metrics).sort().map((k) => kv(k.replace(/^netcoin_/, ''), metrics[k])).join('') || '<p class="muted">Run against a node to populate live metrics.</p>';
    $('#sites').innerHTML = '<div class="mini-list">' + (data.sites?.sites || []).map((s) => '<div class="mini"><b>' + esc(s.site) + '</b><br><small>' + (s.shared_shell ? 'shared shell' : 'missing shell') + ' · ' + (s.index ? 'index ok' : 'missing index') + '</small></div>').join('') + '</div>';
    $('#release').innerHTML = Object.entries(data.release?.checks || {}).map(([k, v]) => kv(k, v ? 'present' : 'missing')).join('') + '<div class="mini"><b>Runbooks</b><br><small>'+esc((live.runbook_actions||[]).join(' · '))+'</small></div><a class="button" href="'+esc(live.diagnostic_bundle||'/api/operator/diagnostics/bundle')+'">Download diagnostics</a>';
    const liveBox = document.querySelector('#liveFeatures'); if (liveBox) liveBox.innerHTML = (data.live_features?.probes || []).map((p) => '<div class="mini"><b>'+esc(p.label)+'</b> '+pill(p.status)+'<br><small>'+esc(p.present)+'/'+esc(p.expected)+' files · '+esc(p.route)+'</small></div>').join('');
  }
  async function refresh() { $('#summaryCards').innerHTML = '<div class="stat"><b>Loading…</b><small>Reading live operator payload</small></div>'; try { const [health,live]=await Promise.all([get('/health-center'),get('/operator/live')]); render(health,live); } catch (e) { $('#summaryCards').innerHTML = '<div class="stat"><b>Offline</b><small>' + esc(e.message) + '</small></div>'; } }
  $('#refresh')?.addEventListener('click', refresh); refresh();
})();
