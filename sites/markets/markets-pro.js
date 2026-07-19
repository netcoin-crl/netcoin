'use strict';
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function api(path, options){const r=await fetch('/api'+path, options);const t=await r.text();let d;try{d=JSON.parse(t)}catch{d={text:t}}; if(!r.ok) throw new Error(d.error||'HTTP '+r.status); return d;}
  const post = (path, body) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  function table(rows, cols){rows=rows||[]; if(!rows.length) return '<p class="muted">No rows yet.</p>'; return '<table class="mini-table"><thead><tr>'+cols.map(c=>'<th>'+esc(c[0])+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(typeof c[1]==='function'?c[1](r):r[c[1]])+'</td>').join('')+'</tr>').join('')+'</tbody></table>';}
  function cents(v){const n=Number(v); if(Number.isFinite(n)) return Math.round(n*100)+'¢'; return esc(v||'—');}
  function traderId(){return new URLSearchParams(location.search).get('trader')||'demo:trader';}
  async function loadMarkets(){try{return (await api('/markets')).markets||[]}catch{return []}}
  function marketId(markets){return new URLSearchParams(location.search).get('market') || markets[0]?.market_id || 'demo';}
  async function renderTrade(){
    const markets=await loadMarkets(); const id=marketId(markets); const market=markets.find(m=>m.market_id===id)||markets[0]||{market_id:id,question:'Sample YES/NO market',outcomes:['YES','NO']};
    let book={}, ticker={}, candles={};
    try{book=await api('/markets/'+encodeURIComponent(id)+'/orderbook')}catch{}
    try{ticker=await api('/markets/'+encodeURIComponent(id)+'/ticker')}catch{}
    try{candles=await api('/markets/'+encodeURIComponent(id)+'/candles?limit=24')}catch{}
    const bids=(book.bids||book.yes_bids||[]).slice(0,12); const asks=(book.asks||book.yes_asks||[]).slice(0,12);
    const outcomeOptions=(market.outcomes||[{outcome_id:'out1',label:'YES'},{outcome_id:'out2',label:'NO'}]).map(o=>'<option value="'+esc(o.outcome_id)+'">'+esc(o.label)+'</option>').join('');
    $('#content').innerHTML='<div class="trader-shell"><section class="trade-card"><h2>'+esc(market.question||market.title||id)+'</h2><div class="metric-row"><span>Mid '+esc(ticker.midpoint_probability??ticker.midpoint??'—')+'</span><span>Spread '+esc(ticker.spread??'—')+'</span><span>Trades '+esc(ticker.trade_count??'—')+'</span></div><div class="chart-placeholder">Live probability history · '+esc((candles.candles||[]).length)+' buckets</div><div class="ladder"><div><h3>YES bids</h3>'+table(bids, [['Price',x=>cents(x.price)],['Size',x=>x.size||x.quantity||0]])+'</div><div><h3>YES asks</h3>'+table(asks, [['Price',x=>cents(x.price)],['Size',x=>x.size||x.quantity||0]])+'</div></div></section><aside class="trade-card"><h2>Order ticket</h2><label>Trader</label><input id="orderTrader" value="'+esc(traderId())+'"><label>Outcome</label><select id="orderOutcome">'+outcomeOptions+'</select><label>Side</label><select id="orderSide"><option value="buy">Buy</option><option value="sell">Sell</option></select><div class="row"><div><label>Price</label><input id="orderPrice" value="0.50"></div><div><label>Shares</label><input id="orderQty" value="10"></div></div><button id="reviewOrder">Review order</button><button id="placeOrder" class="primary">Place order</button><p id="orderMsg" class="muted">Testnet play-money order. Review shows the exact payload before it is sent.</p></aside></div>';
    function orderPayload(){return {trader:$('#orderTrader').value||'demo:trader',outcome_id:$('#orderOutcome').value,side:$('#orderSide').value,price:$('#orderPrice').value,quantity:$('#orderQty').value,time_in_force:'GTC'};}
    $('#reviewOrder')?.addEventListener('click',()=>{$('#orderMsg').innerHTML='Payload to submit:<pre class="mono">'+esc(JSON.stringify(orderPayload(),null,2))+'</pre>';});
    $('#placeOrder')?.addEventListener('click',async()=>{
      $('#orderMsg').textContent='Placing order…';
      try{
        const result=await post('/markets/'+encodeURIComponent(id)+'/order', orderPayload());
        $('#orderMsg').innerHTML='Order placed. Trades: '+esc((result.trades||[]).length)+'.<pre class="mono">'+esc(JSON.stringify(result,null,2))+'</pre>';
        renderTrade();
      }catch(e){$('#orderMsg').textContent='Order failed: '+e.message;}
    });
  }
  async function renderPortfolio(){
    const trader=traderId();
    let p={}; try{p=await api('/markets/portfolio?trader='+encodeURIComponent(trader))}catch{}
    const markets=await loadMarkets();
    const myOrders=[];
    markets.forEach((m)=>{(m.open_orders||[]).forEach((o)=>{if(o.maker===trader||o.taker===trader) myOrders.push(Object.assign({market_id:m.market_id, question:m.question||m.title}, o));});});
    const positionRows=[];
    (p.markets||[]).forEach((m)=>{(m.portfolios||[]).forEach((port)=>{(port.positions||[]).forEach((pos)=>{if(Number(pos.quantity||0)!==0) positionRows.push(Object.assign({market_id:m.market_id}, pos));});});});
    $('#content').innerHTML='<section class="trade-card"><h2>Portfolio</h2><label>Trader</label><input id="traderInput" value="'+esc(trader)+'"><button id="loadPortfolio" class="secondary">Load</button>'+table(positionRows, [['Market',x=>x.market_id],['Outcome',x=>x.label||x.outcome_id],['Shares',x=>x.quantity],['Mark value',x=>x.mark_value],['Unrealized PnL',x=>x.unrealized_pnl]])+'</section><section class="trade-card"><h2>Open orders</h2><div id="openOrdersTable">'+table(myOrders, [['Market',x=>x.market_id],['Outcome',x=>x.outcome_id],['Side',x=>x.side],['Price',x=>x.price],['Remaining',x=>x.remaining??x.quantity],['',x=>'<button type="button" data-cancel="'+esc(x.market_id)+':'+esc(x.order_id)+'">Cancel</button>']])+'</div><p id="portfolioMsg" class="muted"></p></section>';
    $('#loadPortfolio')?.addEventListener('click',()=>{const t=$('#traderInput').value.trim(); location.href='portfolio.html?trader='+encodeURIComponent(t||'demo:trader');});
    $('#openOrdersTable')?.querySelectorAll('[data-cancel]').forEach((btn)=>{
      btn.addEventListener('click',async()=>{
        const [mid,orderId]=btn.getAttribute('data-cancel').split(':');
        if(!orderId){$('#portfolioMsg').textContent='Missing order id.'; return;}
        $('#portfolioMsg').textContent='Cancelling…';
        try{await post('/markets/'+encodeURIComponent(mid)+'/orders/'+encodeURIComponent(orderId)+'/cancel', {trader}); renderPortfolio();}
        catch(e){$('#portfolioMsg').textContent='Cancel failed: '+e.message;}
      });
    });
  }
  function severityClass(sev){ sev=String(sev||'').toLowerCase(); return sev==='critical'?'err':sev==='medium'?'warn':'muted'; }
  function surveillanceCard(surv){
    const s=(surv||{}).surveillance||surv||{};
    const alerts=s.alerts||[];
    const status=s.ok===false?'<span class="err">Alerts open</span>':'<span class="ok">Clear</span>';
    const alertRows=table(alerts, [['Code',x=>x.code||'—'],['Severity',x=>x.severity||'—'],['Detail',x=>x.detail||''],['Ref',x=>x.trade_id||x.trader||x.outcome_id||'']]);
    return '<h3>Surveillance '+status+'</h3><p class="muted">'+esc(s.alert_count||alerts.length||0)+' alert(s) from wash-trade, volume-concentration, and rapid-price-move checks.</p>'+alertRows;
  }
  async function renderDisputes(){
    const markets=await loadMarkets(); const id=marketId(markets); let dossier={}, surv={};
    try{dossier=await api('/markets/'+encodeURIComponent(id)+'/oracles')}catch{}
    try{surv=await api('/markets/'+encodeURIComponent(id)+'/surveillance')}catch{}
    $('#content').innerHTML='<section class="trade-card"><h2>Dispute + evidence panel</h2><p class="muted">Oracle evidence, dispute comments, and surveillance warnings for '+esc(id)+'.</p>'+table(dossier.evidence||[], [['Source',x=>x.source_type||x.type||'evidence'],['Title',x=>x.title||x.url||'—'],['Hash',x=>(x.hash||x.evidence_hash||'').slice(0,16)]])+surveillanceCard(surv)+'</section><section class="trade-card"><h2>Submit evidence</h2><label>Oracle</label><input id="evOracle" value="manual"><label>Title</label><input id="evTitle" placeholder="Official result"><label>URL / note</label><input id="evUrl" placeholder="https://…"><label>Statement</label><textarea id="evStatement" rows="2"></textarea><button id="submitEvidence" class="primary">Submit evidence</button><p id="evidenceMsg" class="muted"></p></section><section class="trade-card"><h2>File dispute</h2><label>Commenter</label><input id="disCommenter" value="operator"><label>Comment</label><textarea id="disComment" rows="2"></textarea><button id="submitDispute" class="primary">File dispute</button><p id="disputeMsg" class="muted"></p></section>';
    $('#submitEvidence')?.addEventListener('click',async()=>{
      $('#evidenceMsg').textContent='Submitting…';
      try{
        await post('/markets/'+encodeURIComponent(id)+'/evidence',{oracle_id:$('#evOracle').value||'manual',title:$('#evTitle').value,evidence_url:$('#evUrl').value,statement:$('#evStatement').value,source_type:'operator_note',submitter:'markets-ui'});
        $('#evidenceMsg').textContent='Evidence submitted.'; renderDisputes();
      }catch(e){$('#evidenceMsg').textContent='Failed: '+e.message;}
    });
    $('#submitDispute')?.addEventListener('click',async()=>{
      $('#disputeMsg').textContent='Submitting…';
      try{
        await post('/markets/'+encodeURIComponent(id)+'/evidence-dispute',{commenter:$('#disCommenter').value||'operator',comment:$('#disComment').value});
        $('#disputeMsg').textContent='Dispute filed.'; renderDisputes();
      }catch(e){$('#disputeMsg').textContent='Failed: '+e.message;}
    });
  }
  async function renderSettlement(){
    const markets=await loadMarkets(); const id=marketId(markets); let r={};
    try{r=await api('/markets/'+encodeURIComponent(id)+'/reconciliation')}catch{}
    const okBadge=r.ok?'<span class="ok">OK</span>':'<span class="warn">Review</span>';
    const summary='<div class="metric-row"><span>Status '+esc(r.status||'—')+'</span><span>Winner '+esc(r.winning_outcome_id||'unresolved')+'</span><span>Claimable '+esc(r.total_claimable||'0')+' NET</span><span>Reserved '+esc(r.reserved||'0')+' NET</span><span>'+okBadge+'</span></div>';
    const negRow=(r.negative_balances||[]).length?'<p class="err">Negative balances: '+esc((r.negative_balances||[]).join(', '))+'</p>':'';
    const rows=table(r.rows||[], [['Trader',x=>x.trader_id||'—'],['Winning shares',x=>x.winning_quantity||0],['Claimable',x=>x.claimable||'0']]);
    $('#content').innerHTML='<section class="trade-card"><h2>Settlement report</h2><p class="muted">Per-trader payout reconciliation for '+esc(id)+'. Winning shares pay out at the fixed unit payout; reserved funds are still locked in open orders.</p>'+summary+negRow+'<h3>Per-trader payouts</h3>'+rows+'</section>';
  }
  const page=document.body.dataset.marketPage; if(page==='portfolio')renderPortfolio(); else if(page==='disputes')renderDisputes(); else if(page==='settlement')renderSettlement(); else renderTrade();
})();
