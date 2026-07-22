'use strict';
(() => {
  const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const $=(s)=>document.querySelector(s);
  async function fetchStatus(){
    for (const path of ['/admin/status','/status','/api/faucet/status']) {
      try { const r=await fetch(path); if (r.ok) return await r.json(); } catch {}
    }
    return {daily_spend_sats:0,daily_cap_sats:100000000,challenge_bits:0,reputation:{},paused:false,recent_requests:[],blocked_requests:[]};
  }
  async function postAdmin(path, body=''){
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});
    const d=await r.json().catch(()=>({})); if(!r.ok) throw new Error(d.error||'admin token required'); return d;
  }
  // A CSSOM write (el.style.width = ...) is not subject to a style-src CSP,
  // unlike an inline style="" attribute injected through innerHTML -- so the
  // meter's fill percentage is set here as a data attribute and applied via
  // JS after render, letting this page run under a strict style-src 'self'.
  function meter(pct){ return '<div class="meter" data-pct="'+pct+'"><i></i></div>'; }
  async function load(){
    const data=await fetchStatus();
    const spent=Number(data.daily_spend_sats||data.daily_cap?.spent_sats||0), cap=Number(data.daily_cap_sats||data.daily_cap?.cap_sats||100000000), difficulty=Number(data.challenge_bits||data.proof_of_work?.difficulty||0);
    const pct=cap?Math.min(100,Math.round(spent/cap*100)):0;
    $('#cards').innerHTML=[['Pause state',data.paused?'Paused':'Active'],['Daily spend',((spent/1e8).toFixed(4))+' / '+((cap/1e8).toFixed(4))+' NET'],['Challenge difficulty',difficulty+' zeroes'],['Recent requests',(data.recent_requests||[]).length],['Blocked requests',(data.blocked_requests||[]).length],['Queue',data.queued||0]].map(x=>'<div class="admin-card"><span class="muted">'+esc(x[0])+'</span><h2>'+esc(x[1])+'</h2>'+(x[0]==='Daily spend'?meter(pct):'')+'</div>').join('');
    document.querySelectorAll('.meter[data-pct] i').forEach((el)=>{ el.style.width = el.parentElement.dataset.pct + '%'; });
    const blocked=(data.blocked_requests||[]).slice(0,80); const reps=Object.entries(data.reputation||{}).slice(0,50);
    $('#abuseRows').innerHTML=blocked.length?blocked.map(x=>'<tr><td>'+esc(x.device||x.ip||'client')+'</td><td>'+esc(x.score??'—')+'</td><td>blocked</td><td>'+esc(x.reason||'—')+'</td></tr>').join(''):(reps.length?reps.map(([k,v])=>'<tr><td>'+esc(k)+'</td><td>'+esc(v.score??0)+'</td><td>'+esc(v.blocked?'blocked':'allow')+'</td><td>'+esc(v.reason||'—')+'</td></tr>').join(''):'<tr><td colspan="4" class="muted">No reputation or blocked-request data yet.</td></tr>');
  }
  window.NetCoinFaucetAdmin={load, pause:()=>postAdmin('/admin/pause').then(load), resume:()=>postAdmin('/admin/resume').then(load), setConfig:(difficulty,cap)=>postAdmin('/admin/config',new URLSearchParams({difficulty,daily_cap_sats:cap}).toString()).then(load)};
  document.addEventListener('DOMContentLoaded', () => {
    $('#btnPause')?.addEventListener('click', () => window.NetCoinFaucetAdmin.pause());
    $('#btnResume')?.addEventListener('click', () => window.NetCoinFaucetAdmin.resume());
    $('#btnSaveControls')?.addEventListener('click', () => window.NetCoinFaucetAdmin.setConfig(
      document.getElementById('powDifficulty').value, document.getElementById('dailyCap').value
    ));
    $('#btnExport')?.addEventListener('click', () => { location.href = '/status'; });
  });
  load();
})();
