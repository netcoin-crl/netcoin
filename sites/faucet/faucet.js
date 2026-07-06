'use strict';

const $ = (s) => document.querySelector(s);
function setText(selector, value) { const el = $(selector); if (el) el.textContent = value; }
function show(selector, value) { const el = $(selector); if (el) el.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
function fmtNet(sats) {
  if (sats === null || sats === undefined) return 'unknown';
  return (Number(sats) / 100000000).toLocaleString(undefined, { maximumFractionDigits: 8 }) + ' NET';
}
function shortHash(value) {
  const text = String(value || '');
  return text.length > 18 ? text.slice(0, 10) + '...' + text.slice(-8) : text;
}
async function fetchJson(path) {
  const r = await fetch(path, { cache: 'no-store' });
  if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
  return r.json();
}
function renderHistory(grants) {
  if (!Array.isArray(grants) || !grants.length) {
    show('#history', 'No recent public grants yet.');
    return;
  }
  const lines = grants.slice(0, 8).map((grant) => {
    const txid = grant.txid || grant.transaction_id || grant.result?.txid || grant.result?.tx?.txid || 'pending';
    const amount = grant.amount || grant.amount_net || '';
    const address = grant.address || '';
    const status = grant.status || 'sent';
    return `${status.padEnd(8)} ${String(amount).padEnd(10)} ${shortHash(address).padEnd(22)} ${shortHash(txid)}`;
  });
  show('#history', ['status   amount     address                txid', ...lines].join('\n'));
}
async function checkFaucet() {
  try {
    const [status, history] = await Promise.all([
      fetchJson('/status').catch(() => fetchJson('/faucet/status')),
      fetchJson('/history').catch(() => fetchJson('/faucet/history')).catch(() => ({ grants: [] })),
    ]);
    const dot = $('#faucetDot'); if (dot) dot.className = 'dot ok';
    setText('#faucetStatus', 'Faucet online');
    setText('#queue', String(status.queued ?? 0));
    const hot = status.hot_wallet || {};
    setText('#hotWallet', hot.state === 'ok' ? fmtNet(hot.spendable_sats) : (hot.state || 'unknown'));
    const captcha = status.captcha || {};
    setText('#captcha', captcha.enabled ? (captcha.provider || 'on') : 'off');
    renderHistory(history.grants);
  } catch (e) {
    const dot = $('#faucetDot'); if (dot) dot.className = 'dot err';
    setText('#faucetStatus', 'Faucet unavailable');
    show('#history', 'Faucet backend is not responding.');
  }
}
const requestButton = $('#requestCoins');
if (requestButton) {
  requestButton.onclick = async () => {
    const address = ($('#address')?.value || '').trim();
    if (!address) { show('#requestResult', 'Enter a NetCoin address first.'); return; }
    const body = new URLSearchParams({ address });
    try {
      const r = await fetch('/faucet', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
      const text = await r.text();
      const clean = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      show('#requestResult', clean.slice(0, 1200));
      checkFaucet();
    } catch (e) { show('#requestResult', 'Request failed: ' + e.message); }
  };
}
const refreshButton = $('#refreshHistory');
if (refreshButton) refreshButton.onclick = checkFaucet;
checkFaucet();
