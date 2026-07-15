'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, options = {}) {
  const r = await fetch('/api' + path, options);
  const t = await r.text();
  let d;
  try {
    d = JSON.parse(t);
  } catch {
    d = { raw: t };
  }
  if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status);
  return d;
}

function statCard(label, value) {
  return `<div class="stat"><div class="k">${esc(label)}</div><div class="v">${esc(value)}</div></div>`;
}

function row(cells) {
  return '<tr>' + cells.map((c) => `<td>${c}</td>`).join('') + '</tr>';
}

let currentDeveloperId = '';

function renderStats(dashboard) {
  const c = dashboard.counts;
  const t = dashboard.totals;
  $('#statsGrid').innerHTML = [
    statCard('Rewards', c.rewards),
    statCard('Withdrawals', c.withdrawals),
    statCard('Payment links', c.payment_links),
    statCard('Invoices', c.invoices),
    statCard('Webhooks', c.webhooks),
    statCard('Webhook events', c.webhook_events),
    statCard('Dead letters', c.webhook_dead_letters),
    statCard('Reward total', t.reward + ' NET'),
    statCard('Withdrawal total', t.withdrawal + ' NET'),
  ].join('');
}

function renderRewards(dashboard) {
  $('#rewardsTable tbody').innerHTML = dashboard.recent_rewards
    .map((r) =>
      row([
        `<span class="mono">${esc(r.reward_id)}</span>`,
        esc(r.player_id || '—'),
        `<span class="mono">${esc(r.address)}</span>`,
        esc(r.amount) + ' NET',
        esc(r.status),
      ])
    )
    .join('') || '<tr><td colspan="5" class="muted">No rewards yet.</td></tr>';
}

function renderWithdrawals(dashboard) {
  $('#withdrawalsTable tbody').innerHTML = dashboard.recent_withdrawals
    .map((w) =>
      row([`<span class="mono">${esc(w.withdrawal_id)}</span>`, `<span class="mono">${esc(w.address)}</span>`, esc(w.amount) + ' NET', esc(w.status)])
    )
    .join('') || '<tr><td colspan="4" class="muted">No withdrawals yet.</td></tr>';
}

function renderLinks(dashboard) {
  $('#linksTable tbody').innerHTML = dashboard.payment_links
    .map((l) =>
      row([
        `<span class="mono">${esc(l.link_id)}</span>`,
        esc(l.title || '—'),
        esc(l.amount) + ' NET',
        esc(l.status),
        `<a href="${esc(l.checkout_url)}">${esc(l.checkout_url)}</a>`,
      ])
    )
    .join('') || '<tr><td colspan="5" class="muted">No payment links yet.</td></tr>';
}

async function loadDeadLetters(developerId) {
  const result = await api('/developer/webhook-events/dead-letters' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
  $('#deadLettersTable tbody').innerHTML = result.dead_letters
    .map((e) => {
      const lastAttempt = (e.attempts || [])[e.attempts.length - 1] || {};
      return row([
        `<span class="mono">${esc(e.event_id)}</span>`,
        esc(e.event),
        esc(e.attempt_count || 0),
        `<span class="err">${esc(lastAttempt.error || lastAttempt.status || '—')}</span>`,
        `<button type="button" class="secondary" data-retry="${esc(e.event_id)}">Retry</button>`,
      ]);
    })
    .join('') || '<tr><td colspan="5" class="muted">No dead letters. Deliveries are healthy.</td></tr>';
  $('#deadLettersTable tbody')
    .querySelectorAll('[data-retry]')
    .forEach((btn) => {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.textContent = 'Retrying…';
        try {
          await api('/developer/webhook-events/deliver', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event_id: btn.dataset.retry }),
          });
        } catch (e) {
          /* fall through — reload shows current state either way */
        }
        await loadDeadLetters(currentDeveloperId);
      });
    });
}

async function loadDeposits(developerId) {
  const result = await api('/developer/deposits' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
  $('#depositsTable tbody').innerHTML = result.deposits
    .map((d) =>
      row([
        `<span class="mono">${esc(d.address)}</span>`,
        `<span class="mono">${esc((d.txid || '').slice(0, 16))}…</span>`,
        esc(d.amount) + ' NET',
        esc(d.confirmations),
        d.ready ? '<span class="ok">yes</span>' : '<span class="muted">pending</span>',
      ])
    )
    .join('') || '<tr><td colspan="5" class="muted">No deposits seen for watched addresses yet.</td></tr>';
}

async function loadPolicy(developerId) {
  try {
    const policy = await api('/developer/funding-policy' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
    $('#policyBody').innerHTML =
      `<div class="stats">` +
      statCard('Daily cap', policy.daily_cap_sats ? policy.daily_cap_sats + ' sats' : 'none') +
      statCard('Per-user cap', policy.per_user_cap_sats ? policy.per_user_cap_sats + ' sats' : 'none') +
      statCard('Allowlist', (policy.allowlisted_addresses || []).length + ' address(es)') +
      statCard('Paused', policy.paused ? 'yes' : 'no') +
      `</div>`;
  } catch (e) {
    $('#policyBody').textContent = 'Unable to load funding policy: ' + e.message;
  }
}

async function loadConsole() {
  const developerId = $('#developerId').value.trim();
  currentDeveloperId = developerId;
  $('#loadMsg').textContent = 'Loading…';
  try {
    const consoleData = await api('/developer/console' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
    $('#consoleBody').style.display = '';
    $('#loadMsg').textContent = '';
    renderStats(consoleData.dashboard);
    renderRewards(consoleData.dashboard);
    renderWithdrawals(consoleData.dashboard);
    renderLinks(consoleData.dashboard);
    $('#sdkOut').textContent = JSON.stringify({ sdk: consoleData.sdk, quick_actions: consoleData.quick_actions }, null, 2);
    await Promise.all([loadDeadLetters(developerId), loadDeposits(developerId), loadPolicy(developerId)]);
  } catch (e) {
    $('#loadMsg').textContent = 'Failed to load console: ' + e.message;
    $('#consoleBody').style.display = 'none';
  }
}

$('#loadBtn').addEventListener('click', loadConsole);
$('#developerId').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter') loadConsole();
});
$('#refreshDeadLetters').addEventListener('click', () => loadDeadLetters(currentDeveloperId));
$('#refreshDeposits').addEventListener('click', () => loadDeposits(currentDeveloperId));

const params = new URLSearchParams(location.search);
const initialDeveloperId = params.get('developer_id') || params.get('id') || '';
if (initialDeveloperId) {
  $('#developerId').value = initialDeveloperId;
  loadConsole();
}
