
'use strict';
const $=s=>document.querySelector(s);const api=async(p,o={})=>{const r=await fetch('/api'+p,o);const t=await r.text();let d;try{d=JSON.parse(t)}catch{d={raw:t}}if(!r.ok||d.error)throw new Error(d.error||('HTTP '+r.status));return d};const show=(e,d)=>{e.textContent=typeof d==='string'?d:JSON.stringify(d,null,2)};function uri(a,memo,amount){const q=new URLSearchParams();if(amount)q.set('amount',amount);if(memo)q.set('message',memo);return `netcoin:${a}${q.toString()?'?'+q.toString():''}`}
async function boot(){try{const l=await api('/latest?n=1'), f=await api('/fee-estimates'), b=(l.blocks||[])[0]||{};$('#nodeDot').className='dot ok';$('#nodeStatus').textContent='Node online';$('#tipHeight').textContent=b.height??'—';$('#lastBlock').textContent=b.hash?b.hash.slice(0,12)+'…':'—';$('#fastFee').textContent=f.presets?.fast?.estimated_fee_sats?f.presets.fast.estimated_fee_sats+' sats':'—'}catch(e){$('#nodeDot').className='dot err';$('#nodeStatus').textContent='Node unreachable'}}
$('#makeRequest').onclick=async()=>{const address=$('#recipient').value.trim(),amount=$('#amount').value.trim(),memo=$('#memo').value.trim();if(!address||!amount){$('#createMsg').textContent='Enter recipient and amount first.';return}try{const inv=await api('/invoices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address,amount,memo,merchant_id:'pay-site',order_id:memo})});$('#createMsg').textContent='Invoice created by NetCoin node.';show($('#requestOut'),inv)}catch(e){$('#createMsg').textContent='Node invoice write unavailable, showing local payment request preview.';show($('#requestOut'),{ok:true,mode:'local-preview',payment_uri:uri(address,memo,amount),recipient_address:address,amount,memo})}};
$('#loadInvoice').onclick=async()=>{const id=$('#invoiceId').value.trim();if(!id)return;try{show($('#invoiceOut'),await api('/invoices/'+encodeURIComponent(id)))}catch(e){show($('#invoiceOut'),{ok:false,error:e.message})}};

/* Hosted checkout: ?invoice=<id> or ?id=<id>, or a /pay/<id> path if the host
   falls back unmatched paths to this page. Renders amount/status/receipt only,
   polls the node so the existing payment.<status> webhook fires as a side effect. */
(function () {
  const QR_L = { 1: { data: 19, ecc: 7, align: [] }, 2: { data: 34, ecc: 10, align: [6, 18] }, 3: { data: 55, ecc: 15, align: [6, 22] }, 4: { data: 80, ecc: 20, align: [6, 26] }, 5: { data: 108, ecc: 26, align: [6, 30] } };
  function gfMul(x, y) { let z = 0; for (let i = 7; i >= 0; i--) { z = ((z << 1) ^ ((z & 0x80) ? 0x11d : 0)) & 0xff; if ((y >>> i) & 1) z ^= x; } return z; }
  function rsGenerator(degree) { let poly = [1]; let root = 1; for (let i = 0; i < degree; i++) { const next = Array(poly.length + 1).fill(0); for (let j = 0; j < poly.length; j++) { next[j] ^= gfMul(poly[j], root); next[j + 1] ^= poly[j]; } poly = next; root = gfMul(root, 2); } return poly.slice(0, degree); }
  function rsRemainder(data, degree) { const gen = rsGenerator(degree); const rem = Array(degree).fill(0); for (const b of data) { const factor = b ^ rem.shift(); rem.push(0); for (let i = 0; i < degree; i++) rem[i] ^= gfMul(gen[i], factor); } return rem; }
  function pushBits(bits, value, length) { for (let i = length - 1; i >= 0; i--) bits.push((value >>> i) & 1); }
  function encodeQrCodewords(text) {
    const bytes = Array.from(new TextEncoder().encode(text));
    let version = 1;
    while (version <= 5 && 4 + 8 + bytes.length * 8 > QR_L[version].data * 8) version++;
    if (version > 5) throw new Error('payment URI is too long for the bundled offline QR renderer');
    const spec = QR_L[version];
    const bits = [];
    pushBits(bits, 0b0100, 4);
    pushBits(bits, bytes.length, 8);
    for (const b of bytes) pushBits(bits, b, 8);
    const cap = spec.data * 8;
    pushBits(bits, 0, Math.min(4, cap - bits.length));
    while (bits.length % 8) bits.push(0);
    const data = [];
    for (let i = 0; i < bits.length; i += 8) data.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));
    for (let pad = 0; data.length < spec.data; pad ^= 1) data.push(pad ? 0x11 : 0xec);
    return { version, codewords: data.concat(rsRemainder(data, spec.ecc)) };
  }
  function makeQrMatrix(text) {
    const { version, codewords } = encodeQrCodewords(text);
    const size = 17 + version * 4;
    const modules = Array.from({ length: size }, () => Array(size).fill(false));
    const reserved = Array.from({ length: size }, () => Array(size).fill(false));
    const set = (x, y, dark, res = true) => { if (x < 0 || y < 0 || x >= size || y >= size) return; modules[y][x] = !!dark; if (res) reserved[y][x] = true; };
    const finder = (x, y) => { for (let dy = -1; dy <= 7; dy++) for (let dx = -1; dx <= 7; dx++) { const xx = x + dx, yy = y + dy; const dark = dx >= 0 && dx <= 6 && dy >= 0 && dy <= 6 && (dx === 0 || dx === 6 || dy === 0 || dy === 6 || (dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4)); set(xx, yy, dark); } };
    finder(0, 0); finder(size - 7, 0); finder(0, size - 7);
    for (let i = 8; i < size - 8; i++) { set(i, 6, i % 2 === 0); set(6, i, i % 2 === 0); }
    if (QR_L[version].align.length) { const pos = QR_L[version].align[1]; for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) { const d = Math.max(Math.abs(dx), Math.abs(dy)); set(pos + dx, pos + dy, d !== 1); } }
    for (let i = 0; i < 9; i++) { reserved[8][i] = true; reserved[i][8] = true; }
    for (let i = 0; i < 8; i++) { reserved[8][size - 1 - i] = true; reserved[size - 1 - i][8] = true; }
    set(8, size - 8, true);
    const bits = [];
    for (const cw of codewords) pushBits(bits, cw, 8);
    let bitIndex = 0; let upward = true;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right--;
      for (let vert = 0; vert < size; vert++) {
        const y = upward ? size - 1 - vert : vert;
        for (let j = 0; j < 2; j++) { const x = right - j; if (reserved[y][x]) continue; let dark = bitIndex < bits.length ? bits[bitIndex++] === 1 : false; if ((x + y) % 2 === 0) dark = !dark; set(x, y, dark, false); }
      }
      upward = !upward;
    }
    let format = 0b01000; let data = format << 10;
    for (let i = 14; i >= 10; i--) if ((data >>> i) & 1) data ^= 0x537 << (i - 10);
    const fmt = ((format << 10) | data) ^ 0x5412;
    const bit = (i) => ((fmt >>> i) & 1) === 1;
    for (let i = 0; i <= 5; i++) set(8, i, bit(i));
    set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
    for (let i = 0; i <= 5; i++) set(5 - i, 8, bit(9 + i));
    for (let i = 0; i <= 7; i++) set(size - 1 - i, 8, bit(i));
    for (let i = 8; i <= 14; i++) set(8, size - 15 + i, bit(i));
    return modules;
  }
  function renderCheckoutQr(uriText) {
    const canvas = $('#checkoutQr'); const msg = $('#checkoutQrMsg');
    if (!canvas || !msg) return;
    const ctx = canvas.getContext('2d');
    try {
      const matrix = makeQrMatrix(uriText);
      const quiet = 4;
      const scale = Math.floor(canvas.width / (matrix.length + quiet * 2));
      const used = (matrix.length + quiet * 2) * scale;
      const offset = Math.floor((canvas.width - used) / 2);
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#000';
      for (let y = 0; y < matrix.length; y++) for (let x = 0; x < matrix.length; x++) if (matrix[y][x]) ctx.fillRect(offset + (x + quiet) * scale, offset + (y + quiet) * scale, scale, scale);
      msg.className = 'muted'; msg.textContent = 'Offline QR generated locally in this browser.';
    } catch (e) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      msg.className = 'err'; msg.textContent = 'QR unavailable: ' + e.message;
    }
  }

  function checkoutInvoiceId() {
    const params = new URLSearchParams(location.search);
    const fromQuery = (params.get('invoice') || params.get('id') || '').trim();
    if (fromQuery) return fromQuery;
    const match = location.pathname.match(/\/pay\/([^/?#]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  const STATUS_LABEL = { unpaid: 'Waiting for payment', pending: 'Payment seen, confirming', confirmed: 'Paid', underpaid: 'Underpaid', overpaid: 'Overpaid (paid)', expired: 'Expired' };
  const TERMINAL_STATUS = new Set(['confirmed', 'overpaid', 'expired']);
  let checkoutTimer = null;

  function renderCheckout(inv) {
    $('#checkoutTitle').textContent = inv.label ? `Payment request for ${inv.label}` : 'Payment request';
    $('#checkoutAmount').textContent = (inv.amount ?? '—') + ' NET';
    $('#checkoutPaid').textContent = (inv.paid_total ?? '0') + ' NET';
    $('#checkoutAddress').textContent = inv.recipient_address || '—';
    $('#checkoutMemo').textContent = inv.memo || inv.order_id || 'No memo';
    $('#checkoutUri').textContent = inv.payment_uri || '';
    $('#checkoutWalletLink').href = inv.payment_uri || 'https://wallet.netcoin.online';
    const status = inv.status || 'unpaid';
    $('#checkoutStatusText').textContent = STATUS_LABEL[status] || status;
    $('#checkoutDot').className = 'dot ' + (status === 'confirmed' || status === 'overpaid' ? 'ok' : status === 'expired' ? 'err' : '');
    $('#checkoutReceipt').textContent = inv.receipt_txid ? `Receipt: ${inv.receipt_txid}` : '';
    if (inv.payment_uri) renderCheckoutQr(inv.payment_uri);
    if (TERMINAL_STATUS.has(status) && checkoutTimer) { clearInterval(checkoutTimer); checkoutTimer = null; }
  }

  async function pollCheckout(id) {
    try { renderCheckout(await api('/invoices/' + encodeURIComponent(id))); }
    catch (e) { $('#checkoutStatusText').textContent = 'Invoice not found'; $('#checkoutDot').className = 'dot err'; if (checkoutTimer) { clearInterval(checkoutTimer); checkoutTimer = null; } }
  }

  function initCheckout() {
    const id = checkoutInvoiceId();
    if (!id) return;
    $('#payHome').style.setProperty('display', 'none', 'important');
    $('#payTools').style.setProperty('display', 'none', 'important');
    $('#customerFlow').style.setProperty('display', 'none', 'important');
    $('#checkout').style.setProperty('display', 'block', 'important');
    pollCheckout(id);
    checkoutTimer = setInterval(() => pollCheckout(id), 4000);
  }

  document.addEventListener('DOMContentLoaded', initCheckout);
  if (document.readyState !== 'loading') initCheckout();
})();

boot();
