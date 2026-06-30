'use strict';

const $ = (s) => document.querySelector(s);

function setText(selector, value) {
  const el = $(selector);
  if (el) el.textContent = value;
}

function show(selector, value) {
  const el = $(selector);
  if (!el) return;
  el.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

async function checkFaucet() {
  try {
    const r = await fetch('/faucet', { method: 'GET', cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);

    const dot = $('#faucetDot');
    if (dot) dot.className = 'dot ok';

    setText('#faucetStatus', 'Faucet online');
    setText('#queue', 'n/a');
    setText('#hotWallet', 'ready');
    setText('#captcha', 'off');

    show('#history', 'History is not available on this faucet backend yet.');
  } catch (e) {
    const dot = $('#faucetDot');
    if (dot) dot.className = 'dot err';

    setText('#faucetStatus', 'Faucet unavailable');
    show('#history', 'Faucet backend is not responding.');
  }
}

const requestButton = $('#requestCoins');
if (requestButton) {
  requestButton.onclick = async () => {
    const address = ($('#address')?.value || '').trim();

    if (!address) {
      show('#requestResult', 'Enter a NetCoin address first.');
      return;
    }

    const body = new URLSearchParams({ address });

    try {
      const r = await fetch('/faucet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body
      });

      const text = await r.text();
      const clean = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      show('#requestResult', clean.slice(0, 1200));
      checkFaucet();
    } catch (e) {
      show('#requestResult', 'Request failed: ' + e.message);
    }
  };
}

const refreshButton = $('#refreshHistory');
if (refreshButton) {
  refreshButton.onclick = checkFaucet;
}

checkFaucet();
