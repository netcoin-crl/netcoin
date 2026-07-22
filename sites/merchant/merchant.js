'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, options = {}) {
  const res = await fetch('/api' + path, options);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok || data.error) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}
function post(path, body) { return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
function out(id, data) { const el = $(id); if (el) el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2); }
function money(v) { return v == null || v === '' ? '—' : String(v); }
function invoiceCard(inv) {
  const id = inv.invoice_id || inv.payment_id || 'invoice';
  const status = inv.status || 'unknown';
  const amount = inv.amount ?? inv.amount_net ?? inv.expected_amount ?? '';
  const rawCheckout = inv.checkout_url || inv.checkout_path || (id ? `/pay/${encodeURIComponent(id)}` : '');
  const checkout = rawCheckout ? (rawCheckout.startsWith('http') ? rawCheckout : `https://pay.netcoin.online${rawCheckout}`) : '';
  return `<article class="invoice"><h3>${esc(id)}</h3><div class="meta"><span>${esc(status)}</span><span>${esc(money(amount))} NET</span><span>${esc(inv.order_id || '')}</span></div><p class="mono">${esc(inv.address || inv.recipient_address || '')}</p>${checkout ? `<a href="${esc(checkout)}" target="_blank" rel="noreferrer">Open checkout</a>` : ''}</article>`;
}
async function loadOverview() {
  try {
    const [latest, invoices, fees] = await Promise.all([api('/latest?n=1'), api('/invoices?limit=20'), api('/fee-estimates')]);
    $('#nodeDot').className = 'dot ok';
    $('#nodeStatus').textContent = 'Merchant API online';
    $('#height').textContent = (latest.blocks || [])[0]?.height ?? '—';
    $('#fastFee').textContent = fees?.presets?.fast?.fee_rate_per_kvb ? String(fees.presets.fast.fee_rate_per_kvb) : '—';
    const list = invoices.invoices || [];
    $('#invoiceCount').textContent = invoices.count ?? list.length;
    $('#invoiceList').innerHTML = list.length ? list.map(invoiceCard).join('') : '<p class="muted">No invoices yet.</p>';
  } catch (e) {
    $('#nodeDot').className = 'dot err';
    $('#nodeStatus').textContent = 'Merchant API needs attention';
    $('#invoiceList').innerHTML = `<p class="err">${esc(e.message)}</p>`;
  }
}
async function createInvoiceFrom(prefix, isPos = false) {
  const merchantId = $('#merchantId')?.value || 'default';
  const payload = {
    merchant_id: merchantId,
    order_id: isPos ? ('pos-' + Date.now()) : $('#orderId').value,
    address: $(prefix + 'Address').value,
    amount: $(prefix + 'Amount').value,
    memo: isPos ? ($('#posMemo').value || 'POS sale') : $('#invoiceMemo').value
  };
  const inv = await post('/invoices', payload);
  const id = inv.invoice_id || inv.payment_id || '';
  const payUrl = id ? `https://pay.netcoin.online/pay/${encodeURIComponent(id)}` : 'https://pay.netcoin.online';
  return { inv, payUrl };
}
$('#createInvoice').onclick = async () => {
  try { const { inv, payUrl } = await createInvoiceFrom('#invoice'); out('#invoiceResult', { invoice: inv, checkout_url: payUrl }); await loadOverview(); }
  catch (e) { out('#invoiceResult', { ok:false, error:e.message }); }
};
$('#createPos').onclick = async () => {
  try {
    const { inv, payUrl } = await createInvoiceFrom('#pos', true);
    $('#posResult').innerHTML = `<b>Checkout ready</b><p><a href="${esc(payUrl)}" target="_blank" rel="noreferrer">${esc(payUrl)}</a></p><p class="mono">${esc(inv.invoice_id || '')}</p>`;
    await loadOverview();
  } catch (e) { $('#posResult').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
};
// /developer/webhooks and /developer/api-keys are the same underlying feature as
// /merchant/webhooks and /merchant/api-keys, but the /merchant/* paths require a
// signed wallet envelope with no signing UI on this page -- these aliases are
// the ones the (keyless) Developer Console already uses successfully.
$('#registerWebhook').onclick = async () => {
  try { out('#webhookResult', await post('/developer/webhooks', { developer_id: $('#merchantId').value || 'default', url: $('#webhookUrl').value })); }
  catch (e) { out('#webhookResult', { ok:false, error:e.message }); }
};
$('#createKey').onclick = async () => {
  try { out('#keyResult', await post('/developer/api-keys', { developer_id: $('#merchantId').value || 'default' })); }
  catch (e) { out('#keyResult', { ok:false, error:e.message }); }
};
$('#createRefund').onclick = async () => {
  const el = $('#refundResult');
  try {
    const refund = await post('/merchant/refunds/plan', { merchant_id: $('#merchantId').value || 'default', invoice_id: $('#refundInvoice').value, address: $('#refundAddress').value, amount: $('#refundAmount').value, reason: $('#refundReason').value });
    const plan = refund.payout_plan || {};
    // A refund never auto-broadcasts -- it's a plan an operator has to
    // review, sign with their own wallet, and broadcast themselves. There's
    // no execute button here on purpose; that's a deliberate non-custodial
    // safeguard, not a missing feature.
    el.innerHTML = `<b>Refund plan created</b> (${esc(refund.refund_id)})<br>Payout ${esc(plan.payout_id || '')} &middot; ${esc(plan.total || '0')} NET &middot; status: ${esc(plan.status || 'unknown')}<br><a href="https://operator.netcoin.online/#payoutsPanel" target="_blank" rel="noreferrer">Review and execute in the Operator dashboard</a>`;
  } catch (e) { el.textContent = 'Failed: ' + e.message; }
};
$('#refreshInvoices').onclick = loadOverview;
$('#loadRecurring').onclick = async () => { try { out('#agreementResult', await api('/recurring')); } catch(e) { out('#agreementResult', { ok:false, error:e.message }); } };
$('#loadEscrows').onclick = async () => { try { out('#agreementResult', await api('/escrows')); } catch(e) { out('#agreementResult', { ok:false, error:e.message }); } };
loadOverview();
