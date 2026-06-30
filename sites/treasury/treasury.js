'use strict';
(async()=>{const out=document.querySelector('#treasuryOut');try{const r=await fetch('/api/treasury',{cache:'no-store'});out.textContent=await r.text()}catch(e){out.textContent='Treasury endpoint unavailable: '+e.message}})();
