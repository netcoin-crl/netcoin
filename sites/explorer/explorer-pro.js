'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmtInt = (v) => Number.isFinite(Number(v)) ? Number(v).toLocaleString('en-US') : '0';
  const fmtSats = (v) => `${fmtInt(v)} sats`;
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

  function kv(k, v) {
    return '<div class="statline"><span>'+esc(k)+'</span><b>'+esc(v)+'</b></div>';
  }

  function table(rows, cols) {
    return '<table class="table"><thead><tr>'+cols.map(c=>'<th>'+esc(c[0])+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(typeof c[1]==='function'?c[1](r):r[c[1]])+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
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

  async function renderAddress(){
    const addr = new URLSearchParams(location.search).get('address') || '';
    $('#addrInput') && ($('#addrInput').value=addr);
    if(!addr){$('#result').innerHTML='<p class="muted">Paste an address to load balance, UTXOs, history, and CSV export.</p>'; return;}
    $('#result').innerHTML='<p class="muted">Loading address…</p>';
    try{
      const d=await api('/explorer/address/'+encodeURIComponent(addr));
      const b=d.balance||{};
      const profile=d.profile||{};
      const utxos=d.utxos||[];
      const history=d.history||[];
      $('#result').innerHTML='<div class="pro-grid"><section class="pro-panel"><h2>Balance</h2>'+kv('Confirmed NET',profile.total||b.total||'0')+kv('Spendable',b.spendable||b.balance_net?.spendable||'0')+kv('UTXOs',utxos.length)+kv('Activity',profile.activity_count||history.length)+'</section><section class="pro-panel"><h2>Exports + Watch</h2><div class="actions"><a href="/api/explorer/address/'+encodeURIComponent(addr)+'/csv">CSV export</a><a href="/api/explorer/watchlist?address='+encodeURIComponent(addr)+'">Watchlist API</a><button id="copyAddr">Copy address</button></div></section></div><section class="pro-panel"><h2>UTXOs</h2>'+table(utxos.slice(0,60), [['Outpoint',u=>(u.txid||u.txid_hex||'')+':'+(u.vout??u.index??0)],['NET',u=>((u.amount||u.amount_sats||0)/1e8).toFixed(8)],['Height','height']])+'</section><section class="pro-panel"><h2>Activity</h2>'+table(history.slice(0,80), [['Tx',h=>h.short_txid||h.txid],['Height','height'],['Confirmations','confirmations'],['Mempool',h=>h.mempool?'yes':'no']])+'</section>';
      $('#copyAddr')?.addEventListener('click',()=>navigator.clipboard?.writeText(addr));
    }catch(e){$('#result').innerHTML='<p class="warn">Address lookup unavailable: '+esc(e.message)+'</p>';}
  }

  async function renderTx(){
    const txid=new URLSearchParams(location.search).get('txid')||'';
    $('#txInput') && ($('#txInput').value=txid);
    if(!txid){$('#result').innerHTML='<p class="muted">Paste a txid to inspect transaction status and raw details.</p>'; return;}
    try{
      const d=await api('/explorer/tx/'+encodeURIComponent(txid));
      $('#result').innerHTML='<section class="pro-panel"><h2>Transaction</h2>'+kv('txid',d.txid||txid)+kv('confirmations',d.confirmations??'pending')+kv('block',d.block_hash||d.block_height||'mempool')+'<pre class="mono">'+esc(JSON.stringify(d,null,2))+'</pre></section>';
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
      $('#result').innerHTML='<div class="pro-grid"><section class="pro-panel"><h2>Live mempool</h2>'+kv('Transactions',depth)+kv('Bytes',fmtInt(d.bytes || 0))+kv('Packages',(d.packages||[]).length)+kv('Min relay',fmtInt(minRelay)+' sats/kvB')+'</section><section class="pro-panel"><h2>Live feed</h2>'+streamState('SSE /api/events/stream ready','live')+kv('Last source',fees.source || 'local policy')+kv('Filtered rows',filtered.length)+'</section></div><section class="pro-panel"><h2>Fee pressure</h2><p class="muted">Percentile bands show observed mempool fee pressure for 10/50/90 percentiles. Empty mempool falls back to min-relay policy.</p>'+feeBandsHtml(fees, txs, minRelay)+'</section><section class="pro-panel"><h2>Pending transactions</h2>'+table(filtered.slice(0,100), [['txid',t=>t.txid||t.id],['fee',t=>fmtSats(t.fee_sats||t.fee||0)],['fee rate',t=>fmtInt(feeRate(t))+' sats/kvB'],['RBF',t=>t.rbf?'yes':'no'],['age',t=>t.age_seconds||'—']])+'</section>';
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
