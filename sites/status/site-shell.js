(() => {
  'use strict';

  const MODE_KEY = 'nc.siteMode.v2';
  const modes = {
    standard: {
      label: 'Standard',
      detail: 'Wallet, Pay, Faucet, Explorer, Learn, and Community first.',
      groups: ['Basics', 'Commerce', 'Build', 'Operate', 'Trust', 'Labs']
    },
    merchant: {
      label: 'Merchant',
      detail: 'Invoices, checkout, API keys, reports, and payment operations first.',
      groups: ['Commerce', 'Basics', 'Build', 'Operate', 'Trust', 'Labs']
    },
    developer: {
      label: 'Developer',
      detail: 'API docs, SDKs, examples, tokens, and integration references first.',
      groups: ['Build', 'Operate', 'Basics', 'Commerce', 'Trust', 'Labs']
    },
    operator: {
      label: 'Operator',
      detail: 'Nodes, network health, status, mining, and release checks first.',
      groups: ['Operate', 'Trust', 'Build', 'Basics', 'Commerce', 'Labs']
    },
    governance: {
      label: 'Governance',
      detail: 'Security, proposals, treasury, public status, and accountability first.',
      groups: ['Trust', 'Operate', 'Basics', 'Build', 'Commerce', 'Labs']
    },
    labs: {
      label: 'Labs',
      detail: 'Experimental markets and advanced demos first, with safety context.',
      groups: ['Labs', 'Trust', 'Build', 'Operate', 'Basics', 'Commerce']
    }
  };

  const links = [
    { href: 'https://netcoin.online', host: 'netcoin.online', label: 'Start', detail: 'public hub', group: 'Basics', primary: true },
    { href: 'https://wallet.netcoin.online', host: 'wallet.netcoin.online', label: 'Wallet', detail: 'send, receive, contacts', group: 'Basics', primary: true },
    { href: 'https://pay.netcoin.online', host: 'pay.netcoin.online', label: 'Pay', detail: 'payment links and receipts', group: 'Basics', primary: true },
    { href: 'https://explorer.netcoin.online', host: 'explorer.netcoin.online', label: 'Explorer', detail: 'blocks, txs, addresses', group: 'Basics', primary: true },
    { href: 'https://learn.netcoin.online', host: 'learn.netcoin.online', label: 'Learn', detail: 'setup and downloads', group: 'Basics', primary: true },
    { href: 'https://faucet.netcoin.online', host: 'faucet.netcoin.online', label: 'Faucet', detail: 'testnet funds', group: 'Basics' },
    { href: 'https://community.netcoin.online', host: 'community.netcoin.online', label: 'Community', detail: 'questions and coordination', group: 'Basics' },
    { href: 'https://learn.netcoin.online#download', host: 'download.netcoin.online', label: 'Download', detail: 'install commands', group: 'Basics' },
    { href: 'https://merchant.netcoin.online', host: 'merchant.netcoin.online', label: 'Merchant', detail: 'checkout and reports', group: 'Commerce' },
    { href: 'https://api.netcoin.online', host: 'api.netcoin.online', label: 'Developers', detail: 'API, SDKs, examples', group: 'Build' },
    { href: 'https://docs.netcoin.online', host: 'docs.netcoin.online', label: 'Docs', detail: 'reference map', group: 'Build' },
    { href: 'https://nodes.netcoin.online', host: 'nodes.netcoin.online', label: 'Nodes', detail: 'seeds and mining', group: 'Operate' },
    { href: 'https://nodes.netcoin.online#network', host: 'nodes.netcoin.online', label: 'Network', detail: 'operator dashboard', group: 'Operate' },
    { href: 'https://status.netcoin.online', host: 'status.netcoin.online', label: 'Status', detail: 'service health', group: 'Operate' },
    { href: 'https://security.netcoin.online', host: 'security.netcoin.online', label: 'Security', detail: 'trust center', group: 'Trust' },
    { href: 'https://governance.netcoin.online', host: 'governance.netcoin.online', label: 'Governance', detail: 'NIPs and voting', group: 'Trust' },
    { href: 'https://treasury.netcoin.online', host: 'treasury.netcoin.online', label: 'Treasury', detail: 'budgets and grants', group: 'Trust' },
    { href: 'https://markets.netcoin.online', host: 'markets.netcoin.online', label: 'Markets Labs', detail: 'experimental demos', group: 'Labs' }
  ];

  const q = (s, r = document) => r.querySelector(s);
  const qa = (s, r = document) => Array.from(r.querySelectorAll(s));
  const currentHost = () => (location.hostname || 'netcoin.online').replace(/^www\./, '');

  function validMode(value) {
    return Object.prototype.hasOwnProperty.call(modes, value) ? value : '';
  }

  function readMode() {
    const params = new URLSearchParams(location.search);
    const urlMode = validMode((params.get('mode') || '').toLowerCase());
    if (urlMode) {
      try { localStorage.setItem(MODE_KEY, urlMode); } catch (e) {}
      return urlMode;
    }
    try {
      return validMode((localStorage.getItem(MODE_KEY) || '').toLowerCase()) || 'standard';
    } catch (e) {
      return 'standard';
    }
  }

  let activeMode = readMode();

  function isCurrent(link) {
    const host = currentHost();
    if (host === link.host) return true;
    if (host === 'download.netcoin.online' && link.label === 'Download') return true;
    if (host === 'developers.netcoin.online' && link.host === 'api.netcoin.online') return true;
    return false;
  }

  function sortedLinks() {
    const order = modes[activeMode].groups;
    const groupIndex = (group) => {
      const index = order.indexOf(group);
      return index === -1 ? order.length : index;
    };
    return links.slice().sort((a, b) => {
      const diff = groupIndex(a.group) - groupIndex(b.group);
      if (diff) return diff;
      return a.label.localeCompare(b.label);
    });
  }

  function directoryHtml() {
    return sortedLinks().map((link) => {
      const active = isCurrent(link) ? ' class="active" aria-current="page"' : '';
      return '<a href="' + link.href + '" data-group="' + link.group + '"' + active + '>' +
        '<span>' + link.label + '</span><small>' + link.group + ' / ' + link.detail + '</small></a>';
    }).join('');
  }

  function settingsHtml() {
    const options = Object.keys(modes).map((key) => {
      const selected = key === activeMode ? ' selected' : '';
      return '<option value="' + key + '"' + selected + '>' + modes[key].label + '</option>';
    }).join('');
    return '<details class="site-settings"><summary>Settings</summary>' +
      '<div class="site-settings-panel">' +
      '<label for="netcoinSiteMode">Site profile</label>' +
      '<select id="netcoinSiteMode" aria-label="Site profile">' + options + '</select>' +
      '<p data-site-mode-help>' + modes[activeMode].detail + '</p>' +
      '<p class="site-settings-note">You can also open any page with <code>?mode=' + activeMode + '</code>. Profile changes reorder the Directory only; they do not hide tools.</p>' +
      '</div></details>';
  }

  function normalizeNav() {
    const nav = q('.site-nav');
    if (!nav) return;
    const primary = links.filter((link) => link.primary || isCurrent(link));
    const seen = new Set();
    const items = primary.filter((link) => {
      if (seen.has(link.label)) return false;
      seen.add(link.label);
      return true;
    }).map((link) => {
      const active = isCurrent(link) ? ' class="active" aria-current="page"' : '';
      return '<a href="' + link.href + '"' + active + '>' + link.label + '</a>';
    }).join('');
    nav.innerHTML = items +
      '<details class="site-tools-more"><summary>Directory</summary><div class="site-more-panel site-tools-more-panel">' + directoryHtml() + '</div></details>' +
      settingsHtml();
  }

  function buildTools() {
    const nav = q('.site-nav');
    if (!nav || q('.site-tools')) return;
    const tools = document.createElement('div');
    tools.className = 'site-tools';
    tools.innerHTML = '<div class="site-context" aria-live="polite"><span>Profile</span><strong data-site-mode-label>' +
      modes[activeMode].label + '</strong><small data-site-mode-copy>' + modes[activeMode].detail + '</small></div>' +
      '<form class="site-search" role="search"><input type="search" aria-label="Search NetCoin" placeholder="Search address, tx, docs, invoice, node..."><button type="submit">Search</button></form>';
    nav.insertAdjacentElement('afterend', tools);
    q('.site-search', tools)?.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const term = q('input', ev.currentTarget).value.trim();
      if (term) routeSearch(term);
    });
  }

  function syncModeUi() {
    document.documentElement.dataset.netcoinMode = activeMode;
    document.body.dataset.netcoinMode = activeMode;
    const profile = modes[activeMode];
    const label = q('[data-site-mode-label]');
    const copy = q('[data-site-mode-copy]');
    const help = q('[data-site-mode-help]');
    const panel = q('.site-more-panel');
    if (label) label.textContent = profile.label;
    if (copy) copy.textContent = profile.detail;
    if (help) help.textContent = profile.detail;
    if (panel) panel.innerHTML = directoryHtml();
  }

  function wireSettings() {
    const select = q('#netcoinSiteMode');
    if (!select) return;
    select.addEventListener('change', () => {
      const next = validMode(select.value) || 'standard';
      activeMode = next;
      try { localStorage.setItem(MODE_KEY, next); } catch (e) {}
      const url = new URL(location.href);
      url.searchParams.set('mode', next);
      history.replaceState(null, '', url.toString());
      syncModeUi();
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
      [/download|install|windows|mac|linux|learn|guide|how/, 'https://learn.netcoin.online#download'],
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

  function buildGithubQuickstart() {
    if (q('[data-github-quickstart]')) return;
    const footer = q('.footer');
    if (!footer) return;
    const section = document.createElement('section');
    section.className = 'github-quickstart card';
    section.dataset.githubQuickstart = '';
    section.innerHTML = '<details><summary>Run NetCoin locally</summary>' +
      '<div class="github-quickstart-grid">' +
      '<div><h2>Install</h2><pre>git clone https://github.com/netcoin-crl/netcoin.git\ncd netcoin\npython3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -e .</pre></div>' +
      '<div><h2>Wallet and mining</h2><pre>python -m netcoin wallet-new --out my-wallet.json --mnemonic\npython -m netcoin miner --node https://api.netcoin.online/api --wallet my-wallet.json --blocks 0 --sync-after\npython tools/check_public_network.py</pre></div>' +
      '<p class="muted github-quickstart-note">Use <code>https://api.netcoin.online/api</code> first. If your network blocks it, use <code>http://18.220.89.128/api</code>. Public-testnet coins have no real-money value.</p>' +
      '</div></details>';
    footer.insertAdjacentElement('beforebegin', section);
  }

  function closeFloatingPanelsOnOutside() {
    document.addEventListener('click', (ev) => {
      qa('.site-tools-more[open], .site-settings[open], .site-more[open]').forEach((d) => {
        if (!d.contains(ev.target)) d.removeAttribute('open');
      });
    });
  }

  window.NetCoinSite = { links, modes, routeSearch };
  normalizeNav();
  buildTools();
  syncModeUi();
  wireSettings();
  buildGithubQuickstart();
  closeFloatingPanelsOnOutside();
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
        var fresh = await ensureKey(true);
        if (fresh) { headers.set("X-Netcoin-Api-Key", fresh); return origFetch(input, init); }
      }
      return res;
    }
    return origFetch(input, init);
  };
})();
