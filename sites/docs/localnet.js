(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function statusLabel(value) {
    if (value === true || value === 'ok' || value === 'available') return 'available';
    if (value === false || value === 'offline') return 'offline';
    return String(value || 'unknown');
  }

  function renderStatus(payload) {
    const services = payload.services || {};
    setText('localnetNodeStatus', statusLabel(services.node_api && services.node_api.status));
    setText('localnetWalletStatus', statusLabel(services.wallet && services.wallet.status));
    setText('localnetFaucetStatus', statusLabel(services.faucet && services.faucet.status));
    setText('localnetExplorerStatus', statusLabel(services.explorer && services.explorer.status));
    setText('localnetStatusJson', JSON.stringify(payload, null, 2));
  }

  async function refreshStatus() {
    try {
      const res = await fetch('/api/localnet/status', { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error('status ' + res.status);
      renderStatus(await res.json());
    } catch (err) {
      renderStatus({
        schema: 'netcoin-localnet-status-v1',
        status: 'static-guide',
        note: 'Serve this page from a local NetCoin app server to enable live localnet checks.',
        error: String((err && err.message) || err),
        services: {
          node_api: { status: 'unknown' },
          wallet: { status: 'guide-only' },
          faucet: { status: 'unknown' },
          explorer: { status: 'unknown' }
        }
      });
    }
  }

  async function copyCommand(ev) {
    const target = ev.currentTarget.getAttribute('data-copy-target');
    const source = target ? document.getElementById(target) : null;
    if (!source) return;
    const text = source.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      ev.currentTarget.textContent = 'Copied';
    } catch (err) {
      ev.currentTarget.textContent = 'Select text to copy';
    }
    window.setTimeout(() => { ev.currentTarget.textContent = ev.currentTarget.dataset.originalLabel || 'Copy'; }, 1600);
  }

  function bindCopyButtons() {
    document.querySelectorAll('[data-copy-target]').forEach((button) => {
      button.dataset.originalLabel = button.textContent;
      button.addEventListener('click', copyCommand);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindCopyButtons();
    $('#btnRefreshLocalnet')?.addEventListener('click', refreshStatus);
    refreshStatus();
  });
})();
