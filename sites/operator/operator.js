'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const ADMIN_TOKEN_KEY = 'nc.operatorAdminToken.v1';
  async function get(path) { const token = localStorage.getItem(ADMIN_TOKEN_KEY) || ''; const r = await fetch('/api' + path, { headers: token ? { 'X-Netcoin-Admin-Token': token } : {} }); const text = await r.text(); let data; let parsed = true; try { data = JSON.parse(text); } catch { parsed = false; data = {}; } if (!r.ok || data.error) throw new Error(parsed ? (data.error || 'HTTP ' + r.status) : 'HTTP ' + r.status + ' (non-JSON response)'); return data; }
  async function post(path, body) {
    const token = localStorage.getItem(ADMIN_TOKEN_KEY) || '';
    const r = await fetch('/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Netcoin-Admin-Token': token }, body: JSON.stringify(body || {}) });
    const text = await r.text();
    let data; try { data = JSON.parse(text); } catch { data = { raw: text }; }
    if (!r.ok || data.error) throw new Error(data.error || ('HTTP ' + r.status));
    return data;
  }
  function pill(status) { return '<span class="pill ' + esc(status || 'partial') + '">' + esc(status || 'partial') + '</span>'; }
  function kv(k, v) { return '<div class="kv"><span>' + esc(k) + '</span><b>' + esc(v) + '</b></div>'; }
  function codeLine(text) { return '<code class="op-code">' + esc(text) + '</code>'; }
  function shortHash(value) { const text = String(value || ''); return text ? text.slice(0, 18) + (text.length > 18 ? '…' : '') : '—'; }
  function runbook(alert){ const key=String(alert.alert||alert.message||'').toLowerCase(); if(key.includes('peer')) return 'Check peerdb, rotate outbound slots, confirm seed reachability.'; if(key.includes('mempool')) return 'Inspect fee floor, spam score, and recent replacements.'; if(key.includes('chain')||key.includes('height')) return 'Compare checkpoints, block time, and public seed tips.'; return 'Open ops bundle, collect logs, and acknowledge incident.'; }
  function renderLedgerAudit(live) {
    const audit = live.ledger_audit || {};
    const state = audit.ok === true ? 'healthy' : (audit.status === 'missing-report' ? 'warning' : 'critical');
    $('#ledgerAudit').innerHTML = '<div class="operator-status-card">' +
      pill(state) +
      kv('Status', audit.status || 'unknown') +
      kv('Rows checked', audit.rows_checked ?? 0) +
      kv('Drift detected', audit.drift_detected ? 'yes' : 'no') +
      (audit.report_path ? kv('Report', audit.report_path) : '<p class="muted">No saved audit report found yet.</p>') +
      '<small>Read-only surface. Generate a fresh report from the operator terminal:</small>' +
      codeLine(audit.command || 'python3 tools/run_ledger_audit.py --ledger accounting.sqlite --out reports/ledger_audit_report.json') +
      '</div>';
  }
  function renderChainstate(live) {
    const cs = live.chainstate || {};
    const digest = cs.chainstate_hash || cs.commitment || cs.digest || cs.hash || '';
    $('#chainstateHash').innerHTML = '<div class="operator-status-card">' +
      pill(cs.ok === false ? 'critical' : 'healthy') +
      kv('Height', cs.height ?? live.height ?? '—') +
      kv('Tip', shortHash(cs.tip_hash || live.tip)) +
      kv('UTXOs', cs.utxo_count ?? cs.utxos ?? '—') +
      kv('Commitment', shortHash(digest)) +
      '<button class="ghost copy-op" type="button" data-copy="' + esc(digest) + '">Copy hash</button>' +
      '</div>';
  }
  function renderAdvertise(live) {
    const adv = live.peer_advertise || {};
    const state = adv.status === 'reachable' ? 'healthy' : (adv.status === 'unreachable' ? 'critical' : 'warning');
    $('#peerAdvertise').innerHTML = '<div class="operator-status-card">' +
      pill(state) +
      kv('Advertised URL', adv.advertise || 'not announced') +
      kv('Reachability', adv.status || 'unknown') +
      kv('Last check', adv.last_check || '—') +
      (adv.error ? '<p class="muted">' + esc(adv.error) + '</p>' : '<p class="muted">Self-advertise is only useful for public nodes with reachable ports.</p>') +
      '</div>';
  }
  function renderMaintenance(live) {
    const m = live.maintenance || {};
    $('#maintenance').innerHTML = '<div class="operator-status-card">' +
      pill(m.backup_available ? 'healthy' : 'warning') +
      kv('Backend', m.backend || 'unknown') +
      kv('Backup available', m.backup_available ? 'yes' : 'no') +
      kv('Latest backup', m.latest_backup || 'none found') +
      '<small>Commands are shown for operator terminal use; destructive browser actions stay disabled.</small>' +
      codeLine(m.backup_command || 'python3 -m netcoin.cli backup --out backups/latest') +
      codeLine(m.reindex_command || 'python3 -m netcoin.cli reindex') +
      '<p class="muted">' + esc(m.restore_note || 'Restore drills remain manual until a report exists.') + '</p>' +
      '</div>';
  }
  function bindCopyButtons() {
    document.querySelectorAll('[data-copy]').forEach((button) => {
      button.addEventListener('click', async () => {
        const value = button.getAttribute('data-copy') || '';
        if (!value) return;
        try {
          await navigator.clipboard.writeText(value);
          button.textContent = 'Copied';
        } catch {
          button.textContent = 'Copy unavailable';
        }
      }, { once: true });
    });
  }
  function render(data, live) {
    $('#summaryCards').innerHTML = [
      ['Product status', data.status, pill(data.status)], ['Height', live.height ?? '—', 'node tip'], ['Peers', (live.peers||[]).length, 'connected/known'], ['Mempool', live.mempool?.count ?? live.mempool?.transactions ?? 0, 'txs'], ['Alerts', data.alerts?.length || 0, (data.alerts?.length ? 'needs review' : 'clear')], ['Fingerprint', String(data.fingerprint || '').slice(0,12), 'health hash']
    ].map(([label, value, note]) => '<div class="stat"><span>' + esc(label) + '</span><b>' + value + '</b><small>' + note + '</small></div>').join('');
    $('#alerts').innerHTML = data.alerts?.length ? data.alerts.map((a) => '<div class="mini">' + pill(a.severity || 'warning') + ' <b>' + esc(a.alert) + '</b><p>' + esc(a.message) + '</p><small>' + esc(runbook(a)) + '</small></div>').join('') : '<p class="muted">No active alerts from the current health-center payload.</p>';
    const metrics = data.metrics || {}; $('#metrics').innerHTML = Object.keys(metrics).sort().map((k) => kv(k.replace(/^netcoin_/, ''), metrics[k])).join('') || '<p class="muted">Run against a node to populate live metrics.</p>';
    $('#sites').innerHTML = '<div class="mini-list">' + (data.sites?.sites || []).map((s) => '<div class="mini"><b>' + esc(s.site) + '</b><br><small>' + (s.shared_shell ? 'shared shell' : 'missing shell') + ' · ' + (s.index ? 'index ok' : 'missing index') + '</small></div>').join('') + '</div>';
    $('#release').innerHTML = Object.entries(data.release?.checks || {}).map(([k, v]) => kv(k, v ? 'present' : 'missing')).join('') + '<div class="mini"><b>Runbooks</b><br><small>'+esc((live.runbook_actions||[]).join(' · '))+'</small></div><a class="button" href="'+esc(live.diagnostic_bundle||'/api/operator/diagnostics/bundle')+'">Download diagnostics</a>';
    renderLedgerAudit(live);
    renderChainstate(live);
    renderAdvertise(live);
    renderMaintenance(live);
    const liveBox = document.querySelector('#liveFeatures'); if (liveBox) liveBox.innerHTML = (data.live_features?.probes || []).map((p) => '<div class="mini"><b>'+esc(p.label)+'</b> '+pill(p.status)+'<br><small>'+esc(p.present)+'/'+esc(p.expected)+' files · '+esc(p.route)+'</small></div>').join('');
    bindCopyButtons();
  }
  async function refresh() { $('#summaryCards').innerHTML = '<div class="stat"><b>Loading…</b><small>Reading live operator payload</small></div>'; try { const [health,live]=await Promise.all([get('/health-center'),get('/operator/live')]); render(health,live); } catch (e) { $('#summaryCards').innerHTML = '<div class="stat"><b>Offline</b><small>' + esc(e.message) + '</small></div>'; } }
  $('#refresh')?.addEventListener('click', refresh); refresh();

  // ---- Payout plans: review, sign (offline, by the operator), broadcast (by
  // the operator), and record it here. This page never holds a key or
  // broadcasts anything itself -- it only reads/writes plan status. ----
  let payoutStatusFilterValue = '';
  const PAYOUT_STATUS_FILTERS = ['', 'pending_operator_review', 'ready_for_wallet_signing', 'signed_ready_to_broadcast', 'broadcast_recorded', 'rejected'];
  function payoutCard(plan) {
    const outputs = (plan.outputs || []).map((o) => '<div class="kv"><span>' + esc(o.address) + '</span><b>' + esc(o.amount) + ' NET</b></div>').join('');
    const canReview = plan.status === 'pending_operator_review';
    const canSign = plan.status === 'ready_for_wallet_signing';
    const canBroadcast = plan.status === 'signed_ready_to_broadcast';
    return '<article class="panel" data-payout-id="' + esc(plan.payout_id) + '" style="margin-bottom:10px">' +
      '<div class="row" style="justify-content:space-between"><b>' + esc(plan.payout_id) + '</b>' + pill(plan.status) + '</div>' +
      '<p class="muted">' + esc(plan.kind || '') + ' &middot; total ' + esc(plan.total) + ' NET' + (plan.memo ? ' &middot; ' + esc(plan.memo) : '') + '</p>' +
      outputs +
      '<div class="row compact-row" style="margin-top:8px">' +
      (canReview ? '<button class="secondary" type="button" data-payout-action="approve" data-payout-id="' + esc(plan.payout_id) + '">Approve</button><button class="secondary" type="button" data-payout-action="reject" data-payout-id="' + esc(plan.payout_id) + '">Reject</button>' : '') +
      (canSign ? '<input placeholder="signed txid" class="payout-txid-input" data-payout-id="' + esc(plan.payout_id) + '" /><button class="secondary" type="button" data-payout-action="signed" data-payout-id="' + esc(plan.payout_id) + '">Record signed</button>' : '') +
      (canBroadcast ? '<input placeholder="broadcast txid" class="payout-txid-input" data-payout-id="' + esc(plan.payout_id) + '" /><button class="secondary" type="button" data-payout-action="broadcasted" data-payout-id="' + esc(plan.payout_id) + '">Record broadcast</button>' : '') +
      '</div>' +
      (plan.broadcast_txid ? '<p class="muted" style="margin-top:6px">Broadcast: ' + esc(shortHash(plan.broadcast_txid)) + '</p>' : '') +
      '</article>';
  }
  async function loadPayouts() {
    const box = $('#payoutList');
    if (!box) return;
    box.innerHTML = 'Loading…';
    try {
      const d = await get('/admin/payouts' + (payoutStatusFilterValue ? '?status=' + encodeURIComponent(payoutStatusFilterValue) : ''));
      const plans = d.payout_plans || [];
      $('#payoutStatusFilter').innerHTML = PAYOUT_STATUS_FILTERS.map((s) =>
        '<button type="button" class="secondary payout-filter-btn' + (s === payoutStatusFilterValue ? ' active' : '') + '" data-payout-filter="' + esc(s) + '">' + esc(s || 'all') + (d.status_counts && d.status_counts[s] ? ' (' + d.status_counts[s] + ')' : '') + '</button>'
      ).join('');
      box.innerHTML = plans.length ? plans.map(payoutCard).join('') : '<p class="muted">No payout plans' + (payoutStatusFilterValue ? ' with this status' : '') + '.</p>';
    } catch (e) {
      box.innerHTML = '<p class="muted">' + esc(e.message) + '</p>';
    }
  }
  $('#btnSaveAdminToken')?.addEventListener('click', () => {
    localStorage.setItem(ADMIN_TOKEN_KEY, $('#operatorAdminToken').value || '');
    $('#operatorAdminToken').value = '';
    $('#operatorAdminToken').placeholder = 'Token saved (hidden)';
  });
  $('#btnRefreshPayouts')?.addEventListener('click', loadPayouts);
  document.addEventListener('click', async (ev) => {
    const filterBtn = ev.target.closest('[data-payout-filter]');
    if (filterBtn) { payoutStatusFilterValue = filterBtn.dataset.payoutFilter || ''; await loadPayouts(); return; }
    const actionBtn = ev.target.closest('[data-payout-action]');
    if (!actionBtn) return;
    const payoutId = actionBtn.dataset.payoutId;
    const action = actionBtn.dataset.payoutAction;
    try {
      if (action === 'approve') await post('/admin/payouts/' + encodeURIComponent(payoutId) + '/review', { approved: true });
      else if (action === 'reject') await post('/admin/payouts/' + encodeURIComponent(payoutId) + '/reject', {});
      else if (action === 'signed' || action === 'broadcasted') {
        const input = document.querySelector('.payout-txid-input[data-payout-id="' + payoutId + '"]');
        const txid = (input?.value || '').trim();
        if (!txid) { alert('Enter a txid first.'); return; }
        await post('/admin/payouts/' + encodeURIComponent(payoutId) + '/' + action, { txid });
      }
      await loadPayouts();
    } catch (e) { alert('Action failed: ' + e.message); }
  });
  loadPayouts();
})();
