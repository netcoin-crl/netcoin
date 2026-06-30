'use strict';
const $ = (s) => document.querySelector(s);
function set(id, value) { const el = $(id); if (el) el.textContent = value; }
async function ok(path) { try { const r = await fetch(path, { cache: 'no-store' }); return r.ok; } catch { return false; } }
(async () => {
  set('#api', await ok('/api/latest?n=1') ? 'Online' : 'Issue');
  set('#faucet', await ok('/faucet') ? 'Online' : 'Issue');
})();
