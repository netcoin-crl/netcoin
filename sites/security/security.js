'use strict';
const rawOut = document.querySelector('#securityOut');
const summary = document.querySelector('#securitySummary') || rawOut;
function esc(v) { return String(v ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function metric(label, value, tone = '') { return `<div class="security-item ${tone}"><b>${esc(label)}</b><span>${esc(value)}</span></div>`; }
async function run() {
  try {
    const r = await fetch('/api/security/status', { cache: 'no-store' });
    const t = await r.text();
    if (!r.ok) throw new Error('Security endpoint protected or unavailable.');
    let d; try { d = JSON.parse(t); } catch { d = null; }
    if (!d) throw new Error('Security endpoint returned non-JSON data.');
    const policy = d.payout_signing_policy || {};
    const rows = [
      metric('Admin token', d.admin_token_required ? 'Required' : 'Public/demo', d.admin_token_required ? 'ok' : 'warn'),
      metric('Storage', `${d.storage_backend || 'unknown'}${d.recommended_storage ? ' / recommended ' + d.recommended_storage : ''}`, d.storage_backend === d.recommended_storage ? 'ok' : 'warn'),
      metric('Payout mode', policy.mode || 'manual_wallet_signing', 'ok'),
      metric('Operator review', policy.require_operator_review ? 'Required' : 'Not required', policy.require_operator_review ? 'ok' : 'warn'),
      metric('Market ack', d.prediction_markets_require_ack ? 'Required' : 'Off', d.prediction_markets_require_ack ? 'ok' : 'warn')
    ].join('');
    summary.innerHTML = rows;
    if (rawOut) rawOut.textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    if (summary) summary.innerHTML = metric('Security check', e.message || 'Unavailable', 'warn');
    if (rawOut) rawOut.textContent = 'Security endpoint unavailable. Public security policy and docs still apply.';
  }
}
run();
