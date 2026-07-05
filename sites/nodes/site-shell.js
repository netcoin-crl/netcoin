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
    simple: 'Simple mode starts at NetCoin Start: wallet, faucet, basic payment links, community, explorer, and download. Advanced areas remain available inside More tools.',
    merchant: 'Merchant mode brings business tools forward: invoices, POS checkout, reports, refunds, API keys, webhooks, and receipts.',
    developer: 'Developer mode brings API docs, SDKs, local development, explorers, test data, and release verification forward.',
    node: 'Node operator mode brings network health, public seeds, mining, status, versions, and run-a-seed guides forward.',
    community: 'Community mode brings discussion, ideas, bounties, governance, voting, roadmap, and contributor tools forward.',
    labs: 'Labs mode brings experimental markets, polls, escrow, contracts, Phase 7 demos, and advanced testnet features forward.'
  };
  const toolLinks = [
    ['https://netcoin.online', 'simple community', 'Start', 'wallet, pay, community basics'],
    ['https://nodes.netcoin.online', 'node developer', 'Network', 'nodes, seeds, status, mining'],
    ['https://api.netcoin.online', 'developer merchant node labs', 'Developers', 'API, SDKs, webhooks, examples'],
    ['https://governance.netcoin.online', 'community node developer labs', 'Governance', 'NIPs, votes, treasury, roadmap'],
    ['https://security.netcoin.online', 'all', 'Security', 'trust center and release safety'],
    ['https://markets.netcoin.online', 'labs', 'Labs', 'experimental market demos'],
    ['https://faucet.netcoin.online', 'simple', 'Faucet', 'request testnet coins'],
    ['https://learn.netcoin.online#download', 'developer node simple', 'Download', 'install from Learn'],
    ['https://api.netcoin.online', 'developer merchant', 'API host', 'machine API endpoint']
  ];
  const q = (s, r = document) => r.querySelector(s);
  const qa = (s, r = document) => Array.from(r.querySelectorAll(s));
  function currentMode() {
    const saved = localStorage.getItem(modeKey) || 'simple';
    return modes[saved] ? saved : 'simple';
  }
  function allowed(el, m) {
    if (el.classList.contains('active')) return true;
    const v = (el.getAttribute('data-modes') || 'all').split(/\s+/).filter(Boolean);
    return v.includes('all') || v.includes(m);
  }
  function moreLinksHtml(extraClass = '') {
    const links = toolLinks.map(([href, dataModes, label, detail]) =>
      '<a href="' + href + '" data-modes="' + dataModes + '">' + label + '<small>' + detail + '</small></a>'
    ).join('');
    return '<div class="site-more-panel ' + extraClass + '">' + links + '</div>';
  }
  function setHint(m) {
    const hint = q('[data-mode-hint]');
    if (!hint) return;
    hint.innerHTML = '<b>' + modes[m] + '</b>: ' + modeHelp[m];
  }
  function applyMode(m) {
    if (!modes[m]) m = 'simple';
    document.documentElement.dataset.netcoinMode = m;
    qa('[data-modes]').forEach((el) => {
      const ok = allowed(el, m);
      const inMore = !!el.closest('.site-more-panel');
      if (inMore) {
        el.classList.remove('mode-hidden');
        el.classList.toggle('mode-dimmed', !ok);
        el.classList.toggle('mode-recommended', ok);
      } else {
        el.classList.toggle('mode-hidden', !ok);
      }
    });
    qa('[data-mode-button]').forEach((btn) => btn.classList.toggle('active', btn.dataset.modeButton === m));
    setHint(m);
  }
  function setMode(m) {
    if (!modes[m]) m = 'simple';
    localStorage.setItem(modeKey, m);
    applyMode(m);
    window.dispatchEvent(new CustomEvent('netcoin:siteModeChanged', { detail: { mode: m, label: modes[m] } }));
  }
  function buildTools() {
    const nav = q('.site-nav');
    if (!nav || q('.site-tools')) return;
    const tools = document.createElement('div');
    tools.className = 'site-tools';
    tools.innerHTML = '<div class="site-tools-main"><div class="site-mode" role="group" aria-label="NetCoin mode"><strong>Mode</strong>' +
      Object.entries(modes).map(([k, v]) => '<button type="button" data-mode-button="' + k + '">' + v + '</button>').join('') +
      '<details class="site-tools-more"><summary>More tools</summary>' + moreLinksHtml('site-tools-more-panel') + '</details>' +
      '</div><div class="mode-hint" data-mode-hint></div></div><form class="site-search" role="search"><input type="search" aria-label="Search NetCoin" placeholder="Search address, tx, docs, invoice, node…"><button type="submit">Search</button></form>';
    nav.insertAdjacentElement('afterend', tools);
    qa('[data-mode-button]', tools).forEach((btn) => btn.addEventListener('click', () => setMode(btn.datasetModeButton || btn.dataset.modeButton)));
    q('.site-search', tools)?.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const term = q('input', ev.currentTarget).value.trim();
      if (term) routeSearch(term);
    });
  }
  function routeSearch(term) {
    const s = term.trim();
    const l = s.toLowerCase();
    let url = 'https://explorer.netcoin.online/?q=' + encodeURIComponent(s);
    const routes = [
      [/wallet|private key|seed phrase|backup|send|receive|contact/, 'https://wallet.netcoin.online'],
      [/start|basic|beginner|home|community basic|pay basic/, 'https://netcoin.online'],
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
    for (const [rx, u] of routes) {
      if (rx.test(l)) { url = u + '?q=' + encodeURIComponent(s); break; }
    }
    location.href = url;
  }
  async function ping() {
    const tools = q('.site-tools');
    if (!tools || q('[data-site-status]')) return;
    const badge = document.createElement('span');
    badge.className = 'site-status-pill';
    badge.dataset.siteStatus = '';
    badge.innerHTML = '<span class="site-status-dot"></span><span>Checking network</span>';
    tools.insertAdjacentElement('afterend', badge);
    try {
      const r = await fetch('/api/latest', { cache: 'no-store' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      q('.site-status-dot', badge).classList.add('ok');
      q('span:last-child', badge).textContent = 'Network online · height ' + ((d.blocks && d.blocks[0] && d.blocks[0].height) || '—');
    } catch (e) {
      q('.site-status-dot', badge).classList.add('err');
      q('span:last-child', badge).textContent = 'API check unavailable';
    }
  }

  function buildGithubQuickstart() {
    if (q('[data-github-quickstart]')) return;
    const footer = q('.footer');
    if (!footer) return;
    const section = document.createElement('section');
    section.className = 'github-quickstart card';
    section.dataset.githubQuickstart = '';
    section.innerHTML = '<details><summary>Run NetCoin from GitHub</summary>' +
      '<div class="github-quickstart-grid">' +
      '<div><h2>Install</h2><pre>git clone https://github.com/netcoin-crl/netcoin.git\ncd netcoin\npython3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -e .</pre></div>' +
      '<div><h2>Wallet and mining</h2><pre>python -m netcoin wallet-new --out my-wallet.json --mnemonic\npython -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 0 --sync-after\npython -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online\npython tools/check_public_network.py</pre></div>' +
      '<p class="muted github-quickstart-note">Preferred API domain: <code>https://api.netcoin.online/api</code>. If a home router, ISP filter, or TLS issue blocks that domain, use <code>http://18.220.89.128/api</code>. Reward schedule: 50 NET starting subsidy, then 20% lower every 210,000 blocks. Legacy, p2sh-segwit, segwit, and taproot are different receiving addresses controlled by the same wallet.</p>' +
      '</div></details>';
    footer.insertAdjacentElement('beforebegin', section);
  }

  function closeMoreOnOutside() {
    document.addEventListener('click', (ev) => {
      qa('.site-more[open], .site-tools-more[open]').forEach((d) => { if (!d.contains(ev.target)) d.removeAttribute('open'); });
    });
  }
  window.NetCoinSiteMode = { currentMode, setMode, applyMode, modes };
  buildTools();
  applyMode(currentMode());
  window.dispatchEvent(new CustomEvent('netcoin:siteModeChanged', { detail: { mode: currentMode(), label: modes[currentMode()] } }));
  // Site-wide network badge removed; network health remains available in Explorer/Network hub.
  buildGithubQuickstart();
  closeMoreOnOutside();
})();

/* NetCoin API-key shim (NIP-0004): the hosted relay requires a free developer
   key for app-layer writes. Transparently register one per browser and attach
   it to same-origin /api POSTs so every NetCoin site keeps working unchanged. */
(function () {
  var KEY_STORE = "nc.apiKey.v1";
  var origFetch = window.fetch.bind(window);
  function isApiWrite(url, method) {
    if (!url) return false;
    var u = String(url);
    var sameOrigin = u.indexOf("/") === 0 ? u : (u.indexOf(location.origin) === 0 ? u.slice(location.origin.length) : "");
    if (!sameOrigin || sameOrigin.indexOf("/api") !== 0) return false;
    if (sameOrigin.indexOf("/keys/register") !== -1) return false;
    return String(method || "GET").toUpperCase() !== "GET";
  }
  async function ensureKey(force) {
    try {
      if (!force) {
        var existing = localStorage.getItem(KEY_STORE);
        if (existing) return existing;
      }
      var r = await origFetch("/api/keys/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ app: "netcoin-site:" + location.hostname }) });
      var d = await r.json();
      if (d && d.api_key) { localStorage.setItem(KEY_STORE, d.api_key); return d.api_key; }
    } catch (e) { /* offline or old node: proceed without a key */ }
    return "";
  }
  window.fetch = async function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var method = (init && init.method) || (input && input.method) || "GET";
    if (isApiWrite(url, method)) {
      var key = await ensureKey(false);
      init = init || {};
      var headers = new Headers(init.headers || (typeof input !== "string" && input && input.headers) || {});
      if (key) headers.set("X-Netcoin-Api-Key", key);
      init.headers = headers;
      var res = await origFetch(input, init);
      if (res.status === 401) {
        var fresh = await ensureKey(true); // stale/revoked key: re-register once
        if (fresh) { headers.set("X-Netcoin-Api-Key", fresh); return origFetch(input, init); }
      }
      return res;
    }
    return origFetch(input, init);
  };
})();
