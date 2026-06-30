(() => {
  'use strict';
  const modeKey = 'nc.siteMode.v1';
  const modes = {
    simple: 'Simple',
    merchant: 'Merchant',
    developer: 'Developer',
    node: 'Node operator',
    community: 'Community',
    labs: 'Labs'
  };
  const modeHelp = {
    simple: 'Simple mode shows wallet, pay, explorer, faucet, learn, and community. More tools stay available in More.',
    merchant: 'Merchant mode emphasizes invoices, POS checkout, reports, refunds, API keys, and webhooks.',
    developer: 'Developer mode emphasizes API docs, SDKs, local development, explorers, and release verification.',
    node: 'Node operator mode emphasizes seeds, status, mining, network health, and running infrastructure.',
    community: 'Community mode emphasizes discussion, ideas, bounties, governance, and roadmap participation.',
    labs: 'Labs mode shows experimental markets, polls, Phase 7 ideas, and advanced testnet features.'
  };
  const allMode = Object.keys(modes);
  const q = (s, r=document) => r.querySelector(s);
  const qa = (s, r=document) => Array.from(r.querySelectorAll(s));
  function currentMode(){return localStorage.getItem(modeKey)||'simple'}
  function setMode(m){localStorage.setItem(modeKey,m); applyMode(m)}
  function allowed(el,m){const v=(el.getAttribute('data-modes')||'all').split(/\s+/); return v.includes('all') || v.includes(m)}
  function applyMode(m){
    document.documentElement.dataset.netcoinMode=m;
    qa('[data-modes]').forEach(el=>{el.classList.toggle('mode-hidden', !allowed(el,m));});
    qa('[data-mode-button]').forEach(btn=>btn.classList.toggle('active',btn.dataset.modeButton===m));
    const hint=q('[data-mode-hint]'); if(hint) hint.innerHTML='<b>'+modes[m]+'</b>: '+modeHelp[m];
  }
  function buildTools(){
    const nav=q('.site-nav'); if(!nav || q('.site-tools')) return;
    const tools=document.createElement('div'); tools.className='site-tools';
    tools.innerHTML='<div><div class="site-mode" role="group" aria-label="NetCoin mode"><strong>Mode</strong>'+Object.entries(modes).map(([k,v])=>'<button type="button" data-mode-button="'+k+'">'+v+'</button>').join('')+'</div><div class="mode-hint" data-mode-hint></div></div><form class="site-search" role="search"><input type="search" aria-label="Search NetCoin" placeholder="Search address, tx, docs, invoice, node…"><button type="submit">Search</button></form>';
    nav.insertAdjacentElement('afterend', tools);
    qa('[data-mode-button]', tools).forEach(btn=>btn.addEventListener('click',()=>setMode(btn.dataset.modeButton)));
    q('.site-search',tools)?.addEventListener('submit', ev=>{ev.preventDefault(); const term=q('input',ev.currentTarget).value.trim(); if(term) routeSearch(term);});
  }
  function routeSearch(term){
    const s=term.trim(); const l=s.toLowerCase(); let url='https://explorer.netcoin.online/?q='+encodeURIComponent(s);
    const routes=[
      [/wallet|private key|seed phrase|backup|send|receive|contact/, 'https://wallet.netcoin.online'],
      [/invoice|checkout|pay|payment|receipt/, 'https://pay.netcoin.online'],
      [/merchant|pos|webhook|api key|refund|report/, 'https://merchant.netcoin.online'],
      [/faucet|test coin/, 'https://faucet.netcoin.online'],
      [/community|discuss|idea|bounty|roadmap/, 'https://community.netcoin.online'],
      [/node|seed|peer|mining|status|network/, 'https://nodes.netcoin.online'],
      [/download|install|windows|mac|linux|learn|guide|how/, 'https://learn.netcoin.online'],
      [/api|developer|sdk|webhook|endpoint/, 'https://api.netcoin.online'],
      [/security|audit|checksum|release|verify|bug/, 'https://security.netcoin.online'],
      [/governance|proposal|treasury|vote|nip/, 'https://governance.netcoin.online'],
      [/market|prediction|lab|phase 7|poll/, 'https://markets.netcoin.online']
    ];
    for(const [rx,u] of routes){if(rx.test(l)){url=u+'?q='+encodeURIComponent(s);break;}}
    location.href=url;
  }
  async function ping(){
    const nav=q('.site-nav'); if(!nav || q('[data-site-status]')) return;
    const badge=document.createElement('span'); badge.className='site-status-pill'; badge.dataset.siteStatus=''; badge.innerHTML='<span class="site-status-dot"></span><span>Checking network</span>'; nav.insertAdjacentElement('afterend', badge);
    try{const r=await fetch('/api/latest',{cache:'no-store'}); if(!r.ok) throw new Error('HTTP '+r.status); const d=await r.json(); q('.site-status-dot',badge).classList.add('ok'); q('span:last-child',badge).textContent='Network online · height '+((d.blocks&&d.blocks[0]&&d.blocks[0].height)||'—');}
    catch(e){q('.site-status-dot',badge).classList.add('err'); q('span:last-child',badge).textContent='API check unavailable';}
  }
  function closeMoreOnOutside(){document.addEventListener('click',ev=>{qa('.site-more[open]').forEach(d=>{if(!d.contains(ev.target)) d.removeAttribute('open')})});}
  buildTools(); applyMode(currentMode()); ping(); closeMoreOnOutside();
})();