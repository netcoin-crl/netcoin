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

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
}
async function solvePow(challenge, difficulty) {
  const prefix = '0'.repeat(Math.max(0, Number(difficulty || 0)));
  if (!challenge || !prefix) return '';
  for (let nonce = 0; nonce < 1000000; nonce += 1) {
    const text = String(nonce);
    const digest = await sha256Hex(`${challenge}:${text}`);
    if (digest.startsWith(prefix)) return text;
  }
  throw new Error('could not solve faucet proof-of-work challenge');
}
async function prepareChallenge() {
  const challenge = await fetchJson('/challenge').catch(() => null);
  if (!challenge || !challenge.enabled) return { challenge: '', nonce: '' };
  setText('#abuseNote', `Solving proof-of-work challenge (${challenge.difficulty} leading zeroes)…`);
  const nonce = await solvePow(challenge.challenge, challenge.difficulty);
  setText('#abuseNote', 'Proof-of-work ready. This helps keep the public faucet online.');
  return { challenge: challenge.challenge, nonce };
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
    const pow = status.proof_of_work || {};
    setText('#powStatus', pow.enabled ? `${pow.difficulty} zeros` : 'off');
    const cap = status.daily_cap || {};
    setText('#dailyCap', cap.cap_sats ? fmtNet(cap.remaining_sats) + ' left' : 'off');
    const abuse = status.abuse || {};
    setText('#abuseNote', abuse.abuse_events_24h ? `${abuse.abuse_events_24h} abuse events blocked today.` : 'Faucet protection is quiet.');
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
    const device = localStorage.getItem('netcoin:faucet-device') || crypto.randomUUID?.() || String(Date.now());
    localStorage.setItem('netcoin:faucet-device', device);
    const challenge = await prepareChallenge();
    const body = new URLSearchParams({ address, device, pow_challenge: challenge.challenge, pow_nonce: challenge.nonce });
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
