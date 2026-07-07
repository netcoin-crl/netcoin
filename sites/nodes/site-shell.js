(() => {
  'use strict';

  const links = [
    { href: 'https://netcoin.online', host: 'netcoin.online', label: 'Start', detail: 'beginner hub', group: 'Basics', primary: true },
    { href: 'https://wallet.netcoin.online', host: 'wallet.netcoin.online', label: 'Wallet', detail: 'send, receive, contacts', group: 'Basics', primary: true },
    { href: 'https://pay.netcoin.online', host: 'pay.netcoin.online', label: 'Pay', detail: 'payment links and receipts', group: 'Basics', primary: true },
    { href: 'https://explorer.netcoin.online', host: 'explorer.netcoin.online', label: 'Explorer', detail: 'blocks, txs, addresses', group: 'Basics', primary: true },
    { href: 'https://learn.netcoin.online', host: 'learn.netcoin.online', label: 'Learn', detail: 'setup and guides', group: 'Basics', primary: true },
    { href: 'https://faucet.netcoin.online', host: 'faucet.netcoin.online', label: 'Faucet', detail: 'testnet coins', group: 'Basics' },
    { href: 'https://community.netcoin.online', host: 'community.netcoin.online', label: 'Community', detail: 'questions and ideas', group: 'Basics' },
    { href: 'https://learn.netcoin.online#download', host: 'download.netcoin.online', label: 'Download', detail: 'install commands', group: 'Basics' },
    { href: 'https://merchant.netcoin.online', host: 'merchant.netcoin.online', label: 'Merchant', detail: 'invoices, POS, reports', group: 'Merchants' },
    { href: 'https://api.netcoin.online', host: 'api.netcoin.online', label: 'Developers', detail: 'API, SDKs, examples', group: 'Builders' },
    { href: 'https://docs.netcoin.online', host: 'docs.netcoin.online', label: 'Docs', detail: 'reference map', group: 'Builders' },
    { href: 'https://nodes.netcoin.online', host: 'nodes.netcoin.online', label: 'Nodes', detail: 'public seeds and mining', group: 'Operators' },
    { href: 'https://network.netcoin.online', host: 'network.netcoin.online', label: 'Network', detail: 'operator dashboard', group: 'Operators' },
    { href: 'https://status.netcoin.online', host: 'status.netcoin.online', label: 'Status', detail: 'service health', group: 'Operators' },
    { href: 'https://security.netcoin.online', host: 'security.netcoin.online', label: 'Security', detail: 'trust and safety', group: 'Trust' },
    { href: 'https://governance.netcoin.online', host: 'governance.netcoin.online', label: 'Governance', detail: 'NIPs and votes', group: 'Trust' },
    { href: 'https://treasury.netcoin.online', host: 'treasury.netcoin.online', label: 'Treasury', detail: 'budgets and grants', group: 'Trust' },
    { href: 'https://markets.netcoin.online', host: 'markets.netcoin.online', label: 'Markets Labs', detail: 'experimental demos', group: 'Labs' }
  ];

  const audienceLinks = [
    ['https://netcoin.online#directory', 'Basics'],
    ['https://merchant.netcoin.online', 'Merchants'],
    ['https://api.netcoin.online', 'Builders'],
    ['https://nodes.netcoin.online', 'Operators'],
    ['https://governance.netcoin.online', 'Governance'],
    ['https://markets.netcoin.online', 'Labs']
  ];

  const q = (s, r = document) => r.querySelector(s);
  const qa = (s, r = document) => Array.from(r.querySelectorAll(s));
  const currentHost = () => (location.hostname || 'netcoin.online').replace(/^www\./, '');
  const isCurrent = (link) => {
    const host = currentHost();
    if (host === link.host) return true;
    if (host === 'download.netcoin.online' && link.label === 'Download') return true;
    if (host === 'developers.netcoin.online' && link.host === 'api.netcoin.online') return true;
    return false;
  };

  function groupedDirectoryHtml() {
    return links.map((link) => {
      const active = isCurrent(link) ? ' class="active" aria-current="page"' : '';
      return '<a href="' + link.href + '" data-group="' + link.group + '"' + active + '>' +
        '<span>' + link.label + '</span><small>' + link.group + ' · ' + link.detail + '</small></a>';
    }).join('');
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
    nav.innerHTML = items + '<details class="site-tools-more"><summary>Directory</summary><div class="site-more-panel site-tools-more-panel">' + groupedDirectoryHtml() + '</div></details>';
  }

  function buildTools() {
    const nav = q('.site-nav');
    if (!nav || q('.site-tools')) return;
    const tools = document.createElement('div');
    tools.className = 'site-tools';
    tools.innerHTML = '<div class="site-tools-main"><div class="site-audience" aria-label="NetCoin audience shortcuts"><strong>For</strong>' +
      audienceLinks.map(([href, label]) => '<a href="' + href + '">' + label + '</a>').join('') +
      '</div></div><form class="site-search" role="search"><input type="search" aria-label="Search NetCoin" placeholder="Search address, tx, docs, invoice, node..."><button type="submit">Search</button></form>';
    nav.insertAdjacentElement('afterend', tools);
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
      '<p class="muted github-quickstart-note">Use <code>https://api.netcoin.online/api</code> first. If your network blocks it, use <code>http://18.220.89.128/api</code>. Testnet coins have no real-money value.</p>' +
      '</div></details>';
    footer.insertAdjacentElement('beforebegin', section);
  }

  function closeDirectoryOnOutside() {
    document.addEventListener('click', (ev) => {
      qa('.site-tools-more[open], .site-more[open]').forEach((d) => {
        if (!d.contains(ev.target)) d.removeAttribute('open');
      });
    });
  }

  window.NetCoinSite = { links, routeSearch };
  normalizeNav();
  buildTools();
  buildGithubQuickstart();
  closeDirectoryOnOutside();
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
