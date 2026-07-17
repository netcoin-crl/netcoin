'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmtInt = (v) => Number.isFinite(Number(v)) ? Number(v).toLocaleString('en-US') : '0';
  const fmtSats = (v) => `${fmtInt(v)} sats`;
  const satsToNet = (v) => (Number(v || 0) / 100000000).toFixed(8);
  const shortHash = (v, n = 12) => {
    const text = String(v || '');
    return text.length > n ? text.slice(0, n) + '…' : text;
  };
  let mempoolStream = null;
  let lastMempoolReload = 0;

  async function api(path) {
    const r = await fetch('/api' + path);
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = { text:t }; }
    if (!r.ok) throw new Error(d.error || 'HTTP '+r.status);
    return d;
  }

  async function postApi(path, payload) {
    const r = await fetch('/api' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {})
    });
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = { text:t }; }
    if (!r.ok || d.ok === false) throw new Error(d.error || 'HTTP '+r.status);
    return d;
  }

  function kv(k, v) {
    return '<div class="statline"><span>'+esc(k)+'</span><b>'+esc(v)+'</b></div>';
  }

  function table(rows, cols, empty = 'No rows yet.') {
    const body = rows.length ? rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(typeof c[1]==='function'?c[1](r):r[c[1]])+'</td>').join('')+'</tr>').join('') : '<tr><td colspan="'+cols.length+'" class="muted">'+esc(empty)+'</td></tr>';
    return '<table class="table"><thead><tr>'+cols.map(c=>'<th>'+esc(c[0])+'</th>').join('')+'</tr></thead><tbody>'+body+'</tbody></table>';
  }

  function normalizeMempoolTransactions(d) {
    const txs = d.transactions || d.txs || d.entries || d.mempool?.entries || [];
    return Array.isArray(txs) ? txs : [];
  }

  function feeRate(tx) {
    return Number(tx.fee_rate_per_kvb ?? tx.feeRatePerKvb ?? tx.fee_rate ?? 0);
  }

  function percentile(values, pct) {
    const ordered = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
    if (!ordered.length) return 0;
    if (ordered.length === 1) return ordered[0];
    const idx = Math.round((Math.max(0, Math.min(100, pct)) / 100) * (ordered.length - 1));
    return ordered[idx];
  }

  function localFeeBands(entries, minRelay) {
    const observed = entries.map(feeRate).filter((rate) => rate > 0);
    const rates = observed.length ? observed : [Number(minRelay || 1000)];
    return {
      p10: { label: '10th percentile', percentile: 10, fee_rate_per_kvb: percentile(rates, 10), estimated_fee_sats: Math.max(1, Math.ceil((percentile(rates, 10) * 200) / 1000)) },
      p50: { label: '50th percentile', percentile: 50, fee_rate_per_kvb: percentile(rates, 50), estimated_fee_sats: Math.max(1, Math.ceil((percentile(rates, 50) * 200) / 1000)) },
      p90: { label: '90th percentile', percentile: 90, fee_rate_per_kvb: percentile(rates, 90), estimated_fee_sats: Math.max(1, Math.ceil((percentile(rates, 90) * 200) / 1000)) }
    };
  }

  function feeBandsHtml(fees, entries, minRelay) {
    const bands = fees?.fee_rate_percentiles || localFeeBands(entries, minRelay);
    return '<div class="fee-bands" aria-label="Mempool fee percentiles">'+['p10','p50','p90'].map((key) => {
      const band = bands[key] || {};
      return '<div class="fee-band"><span>'+esc(band.label || key)+'</span><b>'+fmtInt(band.fee_rate_per_kvb || 0)+'</b><small>sats/kvB · '+fmtSats(band.estimated_fee_sats || 0)+' @ 200 vB</small></div>';
    }).join('')+'</div>';
  }

  function streamState(text, state) {
    const cls = state === 'live' ? 'live' : state === 'warn' ? 'warn' : 'idle';
    return '<div class="live-feed-state '+cls+'" id="liveFeedState"><span class="live-dot" aria-hidden="true"></span><b>'+esc(text)+'</b></div>';
  }

  function startMempoolStream() {
    if (mempoolStream || !('EventSource' in window)) return;
    try {
      mempoolStream = new EventSource('/api/events/stream');
      mempoolStream.addEventListener('netcoin', (event) => {
        const now = Date.now();
        if (now - lastMempoolReload < 1500) return;
        lastMempoolReload = now;
        const target = $('#liveFeedState');
        if (target) target.innerHTML = '<span class="live-dot" aria-hidden="true"></span><b>Live update received</b>';
        try { JSON.parse(event.data || '{}'); } catch { /* best-effort UI refresh only */ }
        renderMempool({ wireStream: false });
      });
      mempoolStream.onerror = () => {
        const target = $('#liveFeedState');
        if (target) target.innerHTML = '<span class="live-dot" aria-hidden="true"></span><b>Polling fallback active</b>';
      };
    } catch {
      mempoolStream = null;
    }
  }

  function bindCopyButtons(root = document) {
    root.querySelectorAll('[data-copy]').forEach((btn) => {
      btn.addEventListener('click', () => navigator.clipboard?.writeText(btn.getAttribute('data-copy') || ''));
    });
  }

  function amountFromUtxo(u) {
    return Number(u.amount_sats ?? u.amount ?? u.output?.amount ?? 0);
  }

  function watchCard(addr) {
    return '<section class="pro-panel phase3-watch"><h2>Watch address</h2><p class="muted">Save this address in the explorer watchlist for quick testnet monitoring.</p><label class="field-label">Optional label</label><input id="watchLabel" placeholder="cold wallet, faucet, miner" autocomplete="off"/><div class="actions"><button id="watchAddressBtn" type="button">Watch address</button><a href="/api/explorer/watchlist?address='+encodeURIComponent(addr)+'">Open watchlist API</a><button id="copyAddr" type="button" data-copy="'+esc(addr)+'">Copy address</button></div><p class="muted" id="watchStatus"></p></section>';
  }

  async function renderAddress(){
    const addr = new URLSearchParams(location.search).get('address') || '';
    $('#addrInput') && ($('#addrInput').value=addr);
    if(!addr){$('#result').innerHTML='<p class="muted">Paste an address to load balance, UTXOs, history, watchlist tools, and CSV export.</p>'; return;}
    $('#result').innerHTML='<p class="muted">Loading address…</p>';
    try{
      const d=await api('/explorer/address/'+encodeURIComponent(addr));
      const b=d.balance||{};
      const profile=d.profile||{};
      const utxos=d.utxos||[];
      const history=d.history||[];
      $('#result').innerHTML='<div class="pro-grid"><section class="pro-panel"><h2>Balance</h2>'+kv('Confirmed NET',profile.total||b.total||'0')+kv('Spendable',b.spendable||b.balance_net?.spendable||'0')+kv('UTXOs',utxos.length)+kv('Activity',profile.activity_count||history.length)+'</section>'+watchCard(addr)+'</div><section class="pro-panel"><h2>UTXO viewer</h2><p class="muted">Spendable and immature outputs currently tracked for this address.</p>'+table(utxos.slice(0,100), [['Outpoint',u=>u.outpoint || ((u.txid||u.txid_hex||'')+':'+(u.vout??u.index??0))],['NET',u=>satsToNet(amountFromUtxo(u))],['Confirmations',u=>u.confirmations ?? '—'],['Status',u=>u.spend_status || (u.coinbase ? 'coinbase' : 'unspent')]], 'No UTXOs for this address yet.')+'</section><section class="pro-panel"><h2>Activity</h2>'+table(history.slice(0,80), [['Tx',h=>h.short_txid||h.txid],['Height','height'],['Confirmations','confirmations'],['Mempool',h=>h.mempool?'yes':'no']], 'No activity yet.')+'</section>';
      $('#copyAddr')?.addEventListener('click',()=>navigator.clipboard?.writeText(addr));
      $('#watchAddressBtn')?.addEventListener('click', async () => {
        const status = $('#watchStatus');
        try {
          const payload = { watch_type: 'address', address: addr, label: $('#watchLabel')?.value || '' };
          const saved = await postApi('/explorer/watchlist', payload);
          if (status) status.textContent = 'Watched: ' + (saved.watch?.label || saved.watch?.value || addr);
        } catch (e) {
          if (status) status.textContent = 'Could not save watch: ' + e.message;
        }
      });
      bindCopyButtons($('#result'));
    }catch(e){$('#result').innerHTML='<p class="warn">Address lookup unavailable: '+esc(e.message)+'</p>';}
  }

  function riskPanel(d) {
    const risk = d.risk || {};
    const warnings = risk.warnings || [];
    const warningRows = warnings.map((w) => '<li><b>'+esc(w.severity || 'warning')+'</b> '+esc(w.message || w.code || 'policy warning')+'</li>').join('') || '<li class="muted">No policy warnings returned.</li>';
    return '<section class="pro-panel tx-risk-panel"><h2>Transaction risk</h2>'+kv('Status', risk.status || (d.confirmed ? 'confirmed' : 'unconfirmed'))+kv('Risk level', risk.risk_level || 'low')+kv('Risk score', risk.risk_score ?? 0)+kv('RBF', risk.rbf ? 'yes' : 'no')+kv('Fee rate', risk.fee_rate_per_kvb ? fmtInt(risk.fee_rate_per_kvb)+' sats/kvB' : '—')+'<ul class="risk-list">'+warningRows+'</ul><p class="muted">Explorer risk is a testnet policy summary, not a final settlement guarantee.</p></section>';
  }

  async function renderTx(){
    const txid=new URLSearchParams(location.search).get('txid')||'';
    $('#txInput') && ($('#txInput').value=txid);
    if(!txid){$('#result').innerHTML='<p class="muted">Paste a txid to inspect transaction status, risk, inputs, outputs, and raw details.</p>'; return;}
    try{
      const d=await api('/explorer/tx/'+encodeURIComponent(txid));
      const tx = d.tx || d.transaction || {};
      const inputs = Array.isArray(tx.inputs) ? tx.inputs : [];
      const outputs = Array.isArray(tx.outputs) ? tx.outputs : [];
      $('#result').innerHTML='<div class="pro-grid"><section class="pro-panel"><h2>Transaction</h2>'+kv('txid',d.txid||txid)+kv('confirmations',d.confirmations??'pending')+kv('block',d.block_hash||d.block_height||'mempool')+kv('inputs / outputs',inputs.length+' / '+outputs.length)+'</section>'+riskPanel(d)+'</div><section class="pro-panel"><h2>Inputs</h2>'+table(inputs.slice(0,100), [['Outpoint',i=>i.coinbase ? 'coinbase' : (i.txid||'')+':'+(i.vout??0)],['Sequence',i=>i.sequence ?? 'final']], 'No inputs.')+'</section><section class="pro-panel"><h2>Outputs</h2>'+table(outputs.slice(0,100), [['Address',o=>o.address||'—'],['NET',o=>satsToNet(o.amount||0)]], 'No outputs.')+'</section><section class="pro-panel"><h2>Raw JSON</h2><pre class="mono">'+esc(JSON.stringify(d,null,2))+'</pre></section>';
    }catch(e){$('#result').innerHTML='<p class="warn">Transaction lookup unavailable: '+esc(e.message)+'</p>';}
  }

  async function renderBlock(){
    const id=new URLSearchParams(location.search).get('block')||'';
    $('#blockInput') && ($('#blockInput').value=id);
    if(!id){$('#result').innerHTML='<p class="muted">Paste a height or hash to inspect block details.</p>'; return;}
    try{
      const d=await api('/explorer/block/'+encodeURIComponent(id));
      $('#result').innerHTML='<section class="pro-panel"><h2>Block</h2>'+kv('height',d.height??id)+kv('hash',d.hash||d.block_hash||'—')+kv('transactions',(d.txs||d.transactions||[]).length)+'<pre class="mono">'+esc(JSON.stringify(d,null,2))+'</pre></section>';
    }catch(e){$('#result').innerHTML='<p class="warn">Block lookup unavailable: '+esc(e.message)+'</p>';}
  }

  async function renderMempool(options = {}){
    const { wireStream = true } = options;
    try{
      const [d, fees] = await Promise.all([
        api('/mempool'),
        api('/fee-estimates').catch(() => ({}))
      ]);
      const q = (new URLSearchParams(location.search).get('q') || '').trim().toLowerCase();
      $('#mempoolInput') && ($('#mempoolInput').value=q);
      const txs = normalizeMempoolTransactions(d);
      const filtered = q ? txs.filter((tx) => String(tx.txid || tx.id || '').toLowerCase().includes(q)) : txs;
      const minRelay = d.min_relay_fee_per_kvb || d.min_fee_rate || 1000;
      const depth = Number(d.size ?? d.count ?? txs.length ?? 0);
      const totalFees = txs.reduce((sum, tx) => sum + Number(tx.fee_sats || tx.fee || 0), 0);
      const rates = txs.map(feeRate).filter((rate) => rate > 0);
      const feeRange = rates.length ? fmtInt(Math.min(...rates))+'-'+fmtInt(Math.max(...rates))+' sats/kvB' : 'empty';
      $('#result').innerHTML='<div class="pro-grid"><section class="pro-panel mempool-status-card"><h2>Mempool status</h2>'+kv('Pending tx count',depth)+kv('Total fees',fmtSats(totalFees))+kv('Fee range',feeRange)+kv('Last updated',new Date().toLocaleTimeString())+'</section><section class="pro-panel"><h2>Live feed</h2>'+streamState('SSE /api/events/stream ready','live')+kv('Last source',fees.source || 'local policy')+kv('Filtered rows',filtered.length)+'</section></div><section class="pro-panel"><h2>Fee pressure</h2><p class="muted">Percentile bands show observed mempool fee pressure for 10/50/90 percentiles. Empty mempool falls back to min-relay policy.</p>'+feeBandsHtml(fees, txs, minRelay)+'</section><section class="pro-panel"><h2>Pending transactions</h2>'+table(filtered.slice(0,100), [['txid',t=>t.txid||t.id],['fee',t=>fmtSats(t.fee_sats||t.fee||0)],['fee rate',t=>fmtInt(feeRate(t))+' sats/kvB'],['RBF',t=>t.rbf?'yes':'no'],['age',t=>t.age_seconds||'—']], 'No unconfirmed transactions.')+'</section>';
      if (wireStream) startMempoolStream();
    }catch(e){$('#result').innerHTML='<p class="warn">Mempool unavailable: '+esc(e.message)+'</p>';}
  }

  function wireForms(){
    document.querySelectorAll('[data-go]').forEach(f=>f.addEventListener('submit',ev=>{
      ev.preventDefault();
      const input=f.querySelector('input');
      location.href=f.dataset.go+'?'+f.dataset.param+'='+encodeURIComponent(input.value.trim());
    }));
  }

  const page=document.body.dataset.explorerPage;
  wireForms();
  if(page==='address') renderAddress();
  if(page==='tx') renderTx();
  if(page==='block') renderBlock();
  if(page==='mempool') renderMempool();
})();
