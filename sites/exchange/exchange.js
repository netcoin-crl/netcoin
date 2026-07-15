'use strict';
(() => {
  const $=(s)=>document.querySelector(s); const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function get(path){const r=await fetch('/api'+path);const text=await r.text();let d;let parsed=true;try{d=JSON.parse(text)}catch{parsed=false;d={}}; if(!r.ok||d.error) throw new Error(parsed?(d.error||'HTTP '+r.status):'HTTP '+r.status+' (non-JSON response)'); return d;}
  function card(label,value,note){return '<div class="card-mini"><span>'+esc(label)+'</span><b>'+esc(value)+'</b><small>'+esc(note||'')+'</small></div>'}
  function row(k,v,c=''){return '<div class="check"><span>'+esc(k)+'</span><b class="'+esc(c)+'">'+esc(v)+'</b></div>'}
  function table(rows, cols){rows=rows||[]; if(!rows.length) return '<p class="muted">No records yet.</p>'; return '<table class="mini-table"><thead><tr>'+cols.map(c=>'<th>'+esc(c[0])+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(typeof c[1]==='function'?c[1](r):r[c[1]])+'</td>').join('')+'</tr>').join('')+'</tbody></table>';}
  function render(health, live){
    const deposits=live.deposits||[], withdrawals=live.withdrawals||[], approvals=live.approval_queue||[], custody=live.custody||{};
    $('#cards').innerHTML=[card('Health',health.status||'partial','product status'),card('Deposits',deposits.length,'tracked'),card('Withdrawals',withdrawals.length,'tracked'),card('Approvals',approvals.length,'pending'),card('Release trust',(health.release?.score||0)+'/'+(health.release?.max_score||0),'tools present')].join('');
    $('#deposits').innerHTML=table(deposits, [['Tx',x=>x.txid||x.deposit_id||'—'],['Status','status'],['Confirmations',x=>x.confirmations??'—'],['Amount',x=>x.amount||x.amount_sats||'—']]);
    $('#withdrawals').innerHTML=table(withdrawals, [['ID',x=>x.withdrawal_id||x.id||'—'],['Status','status'],['To',x=>x.to_address||x.address||'—'],['Amount',x=>x.amount||x.amount_sats||'—']]);
    $('#custody').innerHTML=row('Hot wallet',custody.hot||custody.hot_sats||0)+row('Warm wallet',custody.warm||custody.warm_sats||0)+row('Cold wallet',custody.cold||custody.cold_sats||0)+row('Approval queue',approvals.length, approvals.length?'warn':'ok');
    $('#reserves').innerHTML=[['Reserve attestations',(live.reserve_attestations||[]).length],['Liability proof checker','ready'],['Signed release verification',health.release?.checks?.verify_signature?'ready':'partial'],['Provenance verification',health.release?.checks?.verify_provenance?'ready':'partial']].map(x=>row(x[0],x[1],String(x[1]).includes('partial')?'warn':'ok')).join('');
    $('#riskAlerts').innerHTML=(live.risk_alerts||health.alerts||[]).map(a=>row(a.alert||a.name||'alert',a.severity||a.status||'warning','warn')).join('')||'<p class="muted">No exchange-specific risk alerts.</p>';
  }
  async function refresh(){ $('#cards').innerHTML=card('Loading…','—','Reading live custody state'); try{const [health,live]=await Promise.all([get('/health-center'),get('/exchange/live')]); render(health,live)}catch(e){$('#cards').innerHTML=card('Offline','—',e.message)} }
  $('#refresh')?.addEventListener('click',refresh); refresh();
})();
