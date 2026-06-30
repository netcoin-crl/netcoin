'use strict';
const out=document.querySelector('#securityOut');async function run(){try{const r=await fetch('/api/security/status',{cache:'no-store'});const t=await r.text();out.textContent=r.ok?t:'Security endpoint protected or unavailable. Public docs still apply.'}catch(e){out.textContent='Security endpoint unavailable: '+e.message}}run();
