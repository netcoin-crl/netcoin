'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function getDeveloperId() {
  return ($('#developerId') && $('#developerId').value.trim()) || currentDeveloperId || '';
}

function authHeaders(base = {}) {
  const headers = { ...base };
  const keyInput = $('#developerApiKey');
  const apiKey = keyInput ? keyInput.value.trim() : '';
  if (apiKey) headers['X-Netcoin-Api-Key'] = apiKey;
  return headers;
}

async function api(path, options = {}) {
  const opts = { ...options };
  opts.headers = authHeaders(opts.headers || {});
  const r = await fetch('/api' + path, opts);
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

// ---- signed envelope: /tokens is a sensitive write and needs a signature
// proving control of the creator address. Keys never touch this page.
function canonicalizeForEnvelope(value) {
  if (Array.isArray(value)) return value.map(canonicalizeForEnvelope);
  if (value && typeof value === 'object') {
    const out = {};
    for (const k of Object.keys(value).sort()) out[k] = canonicalizeForEnvelope(value[k]);
    return out;
  }
  return value;
}
async function buildEnvelope(method, path, body, address) {
  const filtered = {};
  for (const k of Object.keys(body)) if (body[k] !== undefined && body[k] !== null) filtered[k] = body[k];
  const bodyStr = JSON.stringify(canonicalizeForEnvelope(filtered));
  const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(bodyStr));
  const bodyHash = Array.from(new Uint8Array(hashBuf)).map((b) => b.toString(16).padStart(2, '0')).join('');
  const timestamp = Math.floor(Date.now() / 1000);
  const nonce = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
  const message = ['NetCoin signed request', 'netcoin-signed-envelope-v1', address, method.toUpperCase(), path, bodyHash, String(timestamp), nonce].join('\n');
  return { message, bodyHash, timestamp, nonce };
}

async function postApi(path, payload) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

function developerPayload(extra = {}) {
  const developerId = getDeveloperId() || 'default';
  return { developer_id: developerId, ...extra };
}

function setResult(selector, value) {
  const el = $(selector);
  if (!el) return;
  el.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function statCard(label, value) {
  return `<div class="stat"><div class="k">${esc(label)}</div><div class="v">${esc(value)}</div></div>`;
}

function row(cells) {
  return '<tr>' + cells.map((c) => `<td>${c}</td>`).join('') + '</tr>';
}

let currentDeveloperId = '';

function formatNet(value) {
  const n = Number(value || 0);
  return (Number.isInteger(n) ? n.toFixed(0) : n.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')) + ' NET';
}

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
    statCard('Reward total', formatNet(t.reward)),
    statCard('Withdrawal total', formatNet(t.withdrawal)),
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

async function loadApiKeys(developerId) {
  const result = await api('/developer/api-keys' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
  const body = $('#apiKeysTable tbody');
  if (!body) return;
  body.innerHTML = result.api_keys
    .map((k) => {
      const active = k.active !== false && !k.revoked_at;
      const action = active ? `<button type="button" class="secondary" data-revoke-key="${esc(k.key_id)}">Revoke</button>` : '';
      return row([
        `<span class="mono">${esc(k.key_id)}</span>`,
        active ? '<span class="ok">active</span>' : '<span class="muted">revoked</span>',
        esc(k.created_at || '—'),
        action,
      ]);
    })
    .join('') || '<tr><td colspan="4" class="muted">No API keys yet.</td></tr>';
  body.querySelectorAll('[data-revoke-key]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Revoking…';
      try {
        const result = await postApi('/developer/api-keys/revoke', developerPayload({ key_id: btn.dataset.revokeKey }));
        setResult('#apiKeyOut', { revoked: result.key_id, active: result.active });
      } catch (e) {
        setResult('#apiKeyOut', 'Failed to revoke key: ' + e.message);
      }
      await loadApiKeys(getDeveloperId());
    });
  });
}

async function loadWebhooks(developerId) {
  const result = await api('/developer/webhooks' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
  const body = $('#webhooksTable tbody');
  if (!body) return;
  body.innerHTML = result.webhooks
    .map((h) =>
      row([
        `<span class="mono">${esc(h.webhook_id)}</span><br><span class="muted">${esc(h.url)}</span>`,
        esc((h.events || []).join(', ')),
        h.active === false ? '<span class="muted">inactive</span>' : '<span class="ok">active</span>',
      ])
    )
    .join('') || '<tr><td colspan="3" class="muted">No webhooks registered yet.</td></tr>';
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
          await postApi('/developer/webhook-events/deliver', { event_id: btn.dataset.retry });
        } catch (e) {
          /* reload shows current state either way */
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
      statCard('Allowlist', String((policy.allowlisted_addresses || []).length)) +
      statCard('Paused', policy.paused ? 'yes' : 'no') +
      `</div>`;
  } catch (e) {
    $('#policyBody').textContent = 'Unable to load funding policy: ' + e.message;
  }
}

async function createPaymentLink() {
  try {
    const result = await postApi('/developer/payment-links', developerPayload({
      address: $('#paymentAddress').value.trim(),
      amount: $('#paymentAmount').value.trim(),
      title: $('#paymentTitle').value.trim() || 'NetCoin payment',
      memo: $('#paymentMemo').value.trim(),
    }));
    setResult('#paymentLinkOut', { link_id: result.link_id, checkout_url: result.checkout_url, payment_uri: result.payment_uri, status: result.status });
    await loadConsole();
  } catch (e) {
    setResult('#paymentLinkOut', 'Failed to create payment link: ' + e.message);
  }
}

async function createApiKey() {
  const box = $('#apiKeyOut');
  try {
    const result = await postApi('/developer/api-keys', developerPayload({ permissions: ['app:write', 'merchant:write', 'webhooks:deliver'] }));
    box.innerHTML =
      `<div class="muted">${esc(result.warning || 'Store this key now. Only its hash is saved.')}</div>` +
      `<div class="api-key-row"><input class="mono" id="newApiKeyField" readonly value="${esc(result.api_key)}" aria-label="New API key" />` +
      `<button type="button" class="secondary" id="copyNewApiKeyBtn">Copy</button></div>` +
      `<div class="muted">key_id: <span class="mono">${esc(result.key_id)}</span></div>`;
    const copyBtn = $('#copyNewApiKeyBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(result.api_key);
          copyBtn.textContent = 'Copied';
          setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
        } catch { /* clipboard permission denied; user can select-and-copy from the field */ }
      });
    }
    await loadApiKeys(getDeveloperId());
  } catch (e) {
    box.textContent = 'Failed to create API key: ' + e.message;
  }
}

function parseEvents(value) {
  return String(value || '')
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function createWebhook() {
  try {
    const payload = developerPayload({
      url: $('#webhookUrl').value.trim(),
      events: parseEvents($('#webhookEvents').value),
    });
    const secret = $('#webhookSecret').value.trim();
    if (secret) payload.secret = secret;
    const result = await postApi('/developer/webhooks', payload);
    setResult('#webhookOut', { webhook_id: result.webhook_id, url: result.url, events: result.events, secret: result.secret, warning: result.warning });
    await Promise.all([loadWebhooks(getDeveloperId()), loadConsole()]);
  } catch (e) {
    setResult('#webhookOut', 'Failed to register webhook: ' + e.message);
  }
}

async function simulateRewards() {
  try {
    const result = await postApi('/developer/simulate/rewards', developerPayload({
      count: Number($('#rewardCount').value || 1),
      amount_sats: Number($('#rewardAmountSats').value || 0),
      withdrawal_threshold_sats: Number($('#withdrawalThresholdSats').value || 0),
    }));
    setResult('#rewardSimOut', {
      simulation_id: result.simulation_id,
      reward_count: result.reward_count,
      total_sats: result.total_sats,
      dust_risk: result.dust_risk,
      estimated_batch_fee_sats: result.estimated_batch_fee_sats,
      recommendation: result.recommendation,
    });
  } catch (e) {
    setResult('#rewardSimOut', 'Failed to simulate rewards: ' + e.message);
  }
}

async function loadConsole() {
  const developerId = getDeveloperId();
  currentDeveloperId = developerId;
  $('#loadMsg').textContent = 'Loading…';
  try {
    const consoleData = await api('/developer/console' + (developerId ? '?developer_id=' + encodeURIComponent(developerId) : ''));
    $('#consoleBody').hidden = false;
    $('#loadMsg').textContent = '';
    renderStats(consoleData.dashboard);
    renderRewards(consoleData.dashboard);
    renderWithdrawals(consoleData.dashboard);
    renderLinks(consoleData.dashboard);
    $('#sdkOut').textContent = JSON.stringify({ sdk: consoleData.sdk, quick_actions: consoleData.quick_actions }, null, 2);
    await Promise.all([
      loadDeadLetters(developerId),
      loadDeposits(developerId),
      loadPolicy(developerId),
      loadApiKeys(developerId),
      loadWebhooks(developerId),
    ]);
  } catch (e) {
    $('#loadMsg').textContent = 'Failed to load console: ' + e.message;
    $('#consoleBody').hidden = true;
  }
}

$('#loadBtn').addEventListener('click', loadConsole);
$('#refreshAllBtn').addEventListener('click', loadConsole);
$('#developerId').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter') loadConsole();
});
$('#refreshDeadLetters').addEventListener('click', () => loadDeadLetters(currentDeveloperId));
$('#refreshDeposits').addEventListener('click', () => loadDeposits(currentDeveloperId));
$('#createPaymentLinkBtn').addEventListener('click', createPaymentLink);
$('#createApiKeyBtn').addEventListener('click', createApiKey);
$('#refreshApiKeysBtn').addEventListener('click', () => loadApiKeys(getDeveloperId()));
$('#createWebhookBtn').addEventListener('click', createWebhook);
$('#refreshWebhooksBtn').addEventListener('click', () => loadWebhooks(getDeveloperId()));
$('#simulateRewardsBtn').addEventListener('click', simulateRewards);

let pendingTokenEnvelope = null;
$('#prepareTokenBtn').addEventListener('click', async () => {
  const out = $('#tokenOut');
  try {
    const creator = $('#tokenCreatorAddr').value.trim();
    if (!creator) throw new Error('creator address is required');
    const body = {
      symbol: $('#tokenSymbol').value.trim().toUpperCase(),
      name: $('#tokenName').value.trim(),
      decimals: Number($('#tokenDecimals').value || 8),
      initial_supply: $('#tokenInitialSupply').value || '0',
      creator,
    };
    const path = '/tokens';
    const envelope = await buildEnvelope('POST', path, body, creator);
    pendingTokenEnvelope = { body, path, envelope, address: creator };
    $('#tokenSignPanel').classList.remove('hide');
    $('#tokenSignMsg').value = envelope.message;
    $('#tokenSignCli').textContent = `python -m netcoin signmessage --wallet your-wallet.json --message "${envelope.message.replace(/"/g, '\\"')}"`;
    out.textContent = 'Ready to sign. Follow the steps below.';
  } catch (e) {
    out.textContent = 'Failed: ' + e.message;
  }
});
$('#copyTokenSignMsg').addEventListener('click', () => navigator.clipboard.writeText($('#tokenSignMsg').value).catch(() => {}));
$('#copyTokenSignCli').addEventListener('click', () => navigator.clipboard.writeText($('#tokenSignCli').textContent).catch(() => {}));
$('#submitTokenBtn').addEventListener('click', async () => {
  const out = $('#tokenOut');
  if (!pendingTokenEnvelope) { out.textContent = 'Prepare the token first.'; return; }
  const sig = $('#tokenSigInput').value.trim();
  if (!sig) { out.textContent = 'Paste a signature first.'; return; }
  try {
    const { body, path, envelope, address } = pendingTokenEnvelope;
    const result = await postApi(path, { ...body, signed_envelope: { address, method: 'POST', path, body_hash: envelope.bodyHash, timestamp: envelope.timestamp, nonce: envelope.nonce, signature: sig } });
    out.textContent = 'Token created: ' + (result.token_id || result.symbol || 'ok');
  } catch (e) {
    out.textContent = 'Failed: ' + e.message;
  }
});

async function loadRateLimitStatus() {
  const summary = $('#rateLimitSummary');
  const tbody = $('#rateLimitTable tbody');
  try {
    const d = await api('/rate-limit-status');
    summary.textContent = `${d.max_requests_per_window} requests / ${d.window_seconds}s window, per IP + API key.`;
    const rows = d.endpoints || [];
    tbody.innerHTML = rows.length
      ? rows.map((r) => `<tr><td>${esc(r.method)}</td><td>${esc(r.path)}</td><td>${esc(r.remaining)} / ${esc(r.capacity)}</td></tr>`).join('')
      : '<tr><td colspan="3" class="muted">No recent requests tracked yet.</td></tr>';
  } catch (e) {
    summary.textContent = 'Failed: ' + e.message;
  }
}
$('#refreshRateLimitBtn')?.addEventListener('click', loadRateLimitStatus);
loadRateLimitStatus();

const params = new URLSearchParams(location.search);
const initialDeveloperId = params.get('developer_id') || params.get('id') || '';
if (initialDeveloperId) {
  $('#developerId').value = initialDeveloperId;
  loadConsole();
}
