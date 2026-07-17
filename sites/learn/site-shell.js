(() => {
  'use strict';

  const MODE_KEY = 'nc.siteMode.v3';
  const modes = {
    user: {
      label: 'User',
      detail: 'Core tools, then network status.',
      groups: ['Core', 'Network', 'Build', 'Ecosystem']
    },
    trader: {
      label: 'Trader',
      detail: 'Markets, portfolio, settlement.',
      groups: ['Core', 'Ecosystem', 'Network', 'Build']
    },
    operator: {
      label: 'Operator',
      detail: 'Health, nodes, custody, releases.',
      groups: ['Network', 'Build', 'Core', 'Ecosystem']
    },
    developer: {
      label: 'Developer',
      detail: 'Docs, API, design, downloads.',
      groups: ['Build', 'Network', 'Core', 'Ecosystem']
    }
  };

  const links = [
    { href: 'https://explorer.netcoin.online', host: 'explorer.netcoin.online', label: 'Explorer', detail: 'verify activity', group: 'Core', primary: true },
    { href: 'https://download.netcoin.online', host: 'download.netcoin.online', label: 'Download', detail: 'install files', group: 'Core', primary: true },
    { href: 'https://netcoin.online', host: 'netcoin.online', label: 'Home', detail: 'testnet hub', group: 'Core', primary: true },
    { href: 'https://markets.netcoin.online', host: 'markets.netcoin.online', label: 'Markets', detail: 'trade test markets', group: 'Core', primary: true },
    { href: 'https://wallet.netcoin.online', host: 'wallet.netcoin.online', label: 'Wallet', detail: 'send and receive', group: 'Core', primary: true },

    { href: 'https://pay.netcoin.online', host: 'pay.netcoin.online', label: 'Pay', detail: 'payment links', group: 'Ecosystem' },
    { href: 'https://merchant.netcoin.online', host: 'merchant.netcoin.online', label: 'Merchant', detail: 'checkout tools', group: 'Ecosystem' },

    { href: 'https://faucet.netcoin.online', host: 'faucet.netcoin.online', label: 'Faucet', detail: 'claim NET', group: 'Network' },
    { href: 'https://nodes.netcoin.online', host: 'nodes.netcoin.online', label: 'Nodes', detail: 'seeds and mining', group: 'Network' },
    { href: 'https://status.netcoin.online', host: 'status.netcoin.online', label: 'Status', detail: 'health', group: 'Network' },
    { href: 'https://operator.netcoin.online', host: 'operator.netcoin.online', label: 'Operator', detail: 'ops health', group: 'Network' },
    { href: 'https://exchange.netcoin.online', host: 'exchange.netcoin.online', label: 'Exchange', detail: 'custody', group: 'Network' },
    { href: 'https://exchange.netcoin.online/listing.html', host: 'exchange.netcoin.online', label: 'Listing Readiness', detail: 'gated checklist', group: 'Network' },
    { href: 'https://security.netcoin.online', host: 'security.netcoin.online', label: 'Security', detail: 'release safety', group: 'Network' },

    { href: 'https://governance.netcoin.online', host: 'governance.netcoin.online', label: 'Governance', detail: 'NIPs and votes', group: 'Ecosystem', adminOnly: true },
    { href: 'https://governance.netcoin.online#treasury', host: 'treasury.netcoin.online', label: 'Treasury', detail: 'grants and spending', group: 'Ecosystem', adminOnly: true },
    { href: 'https://community.netcoin.online', host: 'community.netcoin.online', label: 'Community', detail: 'posts and bounties', group: 'Ecosystem' },
    { href: 'https://learn.netcoin.online', host: 'learn.netcoin.online', label: 'Learn', detail: 'guides', group: 'Ecosystem' },

    { href: 'https://docs.netcoin.online', host: 'docs.netcoin.online', label: 'Docs', detail: 'reference', group: 'Build' },
    { href: 'https://docs.netcoin.online/localnet.html', host: 'docs.netcoin.online', label: 'Localnet', detail: 'launch guide', group: 'Build' },
    { href: 'https://api.netcoin.online', host: 'api.netcoin.online', label: 'API', detail: 'OpenAPI', group: 'Build' },
    { href: 'https://developers.netcoin.online', host: 'developers.netcoin.online', label: 'SDKs', detail: 'client libraries', group: 'Build' },
    { href: 'https://architecture.netcoin.online', host: 'architecture.netcoin.online', label: 'System Design', detail: 'architecture', group: 'Build' },
    { href: 'https://features.netcoin.online', host: 'features.netcoin.online', label: 'Capabilities', detail: 'feature status', group: 'Build' },
    { href: 'https://download.netcoin.online/verify.html', host: 'download.netcoin.online', label: 'Verify Release', detail: 'release checks', group: 'Build' }
  ];

  const navGroups = [
    { title: 'Core', detail: 'main tools' },
    { title: 'Network', detail: 'nodes and health' },
    { title: 'Build', detail: 'docs and APIs' },
    { title: 'Ecosystem', detail: 'governance, community, and commerce' }
  ];

  const featureGroups = [
    {
      title: 'Core',
      items: [
        ['Explorer', 'https://explorer.netcoin.online'],
        ['Download', 'https://download.netcoin.online'],
        ['Home', 'https://netcoin.online'],
        ['Markets', 'https://markets.netcoin.online'],
        ['Wallet', 'https://wallet.netcoin.online']
      ]
    },
    {
      title: 'Network',
      items: [
        ['Faucet', 'https://faucet.netcoin.online'],
        ['Nodes', 'https://nodes.netcoin.online'],
        ['Status', 'https://status.netcoin.online'],
        ['Operator', 'https://operator.netcoin.online'],
        ['Exchange', 'https://exchange.netcoin.online'],
        ['Listing Readiness', 'https://exchange.netcoin.online/listing.html'],
        ['Security', 'https://security.netcoin.online']
      ]
    },
    {
      title: 'Build',
      items: [
        ['Docs', 'https://docs.netcoin.online'],
        ['Localnet', 'https://docs.netcoin.online/localnet.html'],
        ['API', 'https://api.netcoin.online'],
        ['SDKs', 'https://developers.netcoin.online'],
        ['System Design', 'https://architecture.netcoin.online'],
        ['Capabilities', 'https://features.netcoin.online'],
        ['Verify Release', 'https://download.netcoin.online/verify.html']
      ]
    },
    {
      title: 'Ecosystem',
      items: [
        ['Governance', 'https://governance.netcoin.online'],
        ['Treasury', 'https://governance.netcoin.online#treasury'],
        ['NIPs', 'https://governance.netcoin.online'],
        ['Roadmap', 'https://governance.netcoin.online#roadmap'],
        ['Community', 'https://community.netcoin.online'],
        ['Ideas', 'https://community.netcoin.online#ideas'],
        ['Bounties', 'https://community.netcoin.online#bounties'],
        ['Learn', 'https://learn.netcoin.online'],
        ['Pay', 'https://pay.netcoin.online'],
        ['Merchant', 'https://merchant.netcoin.online']
      ]
    }
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
      return validMode((localStorage.getItem(MODE_KEY) || '').toLowerCase()) || 'user';
    } catch (e) {
      return 'user';
    }
  }

  let activeMode = readMode();

  // Admin/Simple view: orthogonal to the persona mode above (which only
  // reorders nav groups). This controls content density -- Simple (the
  // default for anyone without the flag set) hides admin-only-tagged nav
  // links (Treasury, Governance -- pure read/vote pages with no everyday
  // action) and lets pages opt individual blocks out via [data-admin-only].
  // Admin shows everything, i.e. today's full site.
  const VIEW_KEY = 'nc.viewLevel.v1';
  function readViewLevel() {
    const params = new URLSearchParams(location.search);
    const urlView = (params.get('view') || '').toLowerCase();
    if (urlView === 'admin' || urlView === 'simple') {
      try { localStorage.setItem(VIEW_KEY, urlView); } catch (e) {}
      return urlView;
    }
    try {
      const stored = (localStorage.getItem(VIEW_KEY) || '').toLowerCase();
      return stored === 'admin' ? 'admin' : 'simple';
    } catch (e) {
      return 'simple';
    }
  }
  let viewLevel = readViewLevel();
  function applyViewLevel() {
    document.body.dataset.ncView = viewLevel;
  }
  function setViewLevel(next) {
    viewLevel = next === 'admin' ? 'admin' : 'simple';
    try { localStorage.setItem(VIEW_KEY, viewLevel); } catch (e) {}
    applyViewLevel();
    normalizeNav();
    const btn = q('#ncViewToggle');
    if (btn) btn.textContent = viewLevel === 'admin' ? 'Admin view' : 'Simple view';
  }
  function buildViewToggle() {
    if (q('#ncViewToggle')) return;
    const btn = document.createElement('button');
    btn.id = 'ncViewToggle';
    btn.type = 'button';
    btn.className = 'nc-view-toggle';
    btn.title = 'Switch between the simplified view and the full admin view';
    btn.textContent = viewLevel === 'admin' ? 'Admin view' : 'Simple view';
    btn.addEventListener('click', () => setViewLevel(viewLevel === 'admin' ? 'simple' : 'admin'));
    document.body.appendChild(btn);
  }

  function isCurrent(link) {
    const host = currentHost();
    if (host === link.host) return true;
    if (host === 'download.netcoin.online' && link.label === 'Download') return true;
    if (host === 'developers.netcoin.online' && link.host === 'api.netcoin.online') return true;
    return false;
  }

  function sortedGroups() {
    const order = modes[activeMode].groups;
    return navGroups.slice().sort((a, b) => {
      const ai = order.indexOf(a.title);
      const bi = order.indexOf(b.title);
      const left = ai === -1 ? order.length : ai;
      const right = bi === -1 ? order.length : bi;
      return left - right;
    });
  }

  function sortedLinks(group) {
    let groupLinks = links.filter((link) => link.group === group);
    if (viewLevel === 'simple') groupLinks = groupLinks.filter((link) => !link.adminOnly);
    if (group === 'Core') {
      const order = ['Home', 'Wallet', 'Explorer', 'Markets', 'Download'];
      return groupLinks.sort((a, b) => order.indexOf(a.label) - order.indexOf(b.label));
    }
    const order = modes[activeMode].groups;
    const groupIndex = (value) => {
      const index = order.indexOf(value);
      return index === -1 ? order.length : index;
    };
    return groupLinks.sort((a, b) => {
      const diff = groupIndex(a.group) - groupIndex(b.group);
      if (diff) return diff;
      return a.label.localeCompare(b.label);
    });
  }

  const primaryNavLabels = ['Home', 'Wallet', 'Explorer', 'Markets'];

  function directoryHtml(includePrimaryCore = true) {
    return sortedGroups().map((group) => {
      let groupLinks = sortedLinks(group.title);
      if (!includePrimaryCore && group.title === 'Core') {
        groupLinks = groupLinks.filter((link) => primaryNavLabels.indexOf(link.label) === -1);
      }
      if (!groupLinks.length) return '';
      const activeGroup = groupLinks.some(isCurrent) ? ' active' : '';
      const items = groupLinks.map((link) => {
        const active = isCurrent(link) ? ' class="active" aria-current="page"' : '';
        return '<a href="' + link.href + '" data-group="' + link.group + '"' + active + '>' +
          '<span>' + link.label + '</span><small>' + link.detail + '</small></a>';
      }).join('');
      return '<section class="site-more-group' + activeGroup + '" aria-label="' + group.title + '">' +
        '<h3>' + group.title + '<small>' + group.detail + '</small></h3><div>' + items + '</div></section>';
    }).join('');
  }

  function settingsHtml() {
    return '';
  }

  function coreTabsHtml() {
    return sortedLinks('Core').filter((link) => primaryNavLabels.indexOf(link.label) !== -1).map((link) => {
      const active = isCurrent(link) ? ' class="active" aria-current="page"' : '';
      return '<a href="' + link.href + '" data-group="Core"' + active + '>' + link.label + '</a>';
    }).join('');
  }

  function categoryTabsHtml() {
    const groupedPanels = sortedGroups().filter((group) => group.title !== 'Core');
    if (!groupedPanels.length) return '';
    const activeExtra = links.some((link) => isCurrent(link) && primaryNavLabels.indexOf(link.label) === -1) ? ' open' : '';
    return '<details class="site-nav-group site-nav-more' + activeExtra + '"><summary>More</summary>' +
      '<div class="site-nav-panel site-nav-panel-wide">' + directoryHtml(false) + '</div></details>';
  }

  function normalizeNav() {
    const nav = q('.site-nav');
    if (!nav) return;
    nav.innerHTML = coreTabsHtml() + categoryTabsHtml() + settingsHtml();
  }

  function buildTools() {
    const nav = q('.site-nav');
    if (!nav || q('.site-tools')) return;
    const tools = document.createElement('div');
    tools.className = 'site-tools site-tools-compact';
    tools.innerHTML = '<form class="site-search" role="search"><input type="search" aria-label="Search addresses, transactions, markets, or docs" placeholder="Search address, tx, market, or docs…"><button type="submit" aria-label="Search">Go</button></form>';
    nav.insertAdjacentElement('afterend', tools);
    q('.site-search', tools)?.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const term = q('input', ev.currentTarget).value.trim();
      if (term) routeSearch(term);
    });
  }

  function buildFeatureDock() {
    const tools = q('.site-tools');
    if (!tools || q('.feature-dock')) return;
    const dock = document.createElement('details');
    dock.className = 'feature-dock feature-dock-compact';
    dock.setAttribute('aria-label', 'NetCoin directory');
    dock.innerHTML = '<summary>Directory</summary><div class="feature-dock-panel">' + featureGroups.map((group) => {
      const items = group.items.map((item) => '<a href="' + item[1] + '">' + item[0] + '</a>').join('');
      return '<div class="feature-group"><b>' + group.title + '</b><div>' + items + '</div></div>';
    }).join('') + '</div>';
    tools.insertAdjacentElement('afterend', dock);
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
    return;
  }

  function routeSearch(term) {
    const s = term.trim();
    if (!s) return;
    const l = s.toLowerCase();
    // Chain-data lookups go straight to the explorer's real hash router
    // (#/address, #/tx, #/block) -- explorer-app.js never reads a `?q=`
    // param, so anything else here would land on a page that ignores it.
    if (/^\d+$/.test(s)) { location.href = 'https://explorer.netcoin.online/#/block/' + encodeURIComponent(s); return; }
    if (/^[0-9a-fA-F]{64}$/.test(s)) { location.href = 'https://explorer.netcoin.online/#/tx/' + encodeURIComponent(s); return; }
    if (/^net1[a-z0-9]{20,}$/i.test(s) || (/^[A-Za-z0-9]{26,40}$/.test(s) && !/^[0-9a-fA-F]{64}$/.test(s))) {
      location.href = 'https://explorer.netcoin.online/#/address/' + encodeURIComponent(s);
      return;
    }
    const routes = [
      [/feature|rating|score|catalog|all tools|directory/, 'https://features.netcoin.online'],
      [/wallet|private key|seed phrase|backup|send|receive|contact|rbf|speed up|fee preset|psbt|multisig/, 'https://wallet.netcoin.online'],
      [/start|basic|beginner|home|community basic|pay basic/, 'https://netcoin.online'],
      [/invoice|checkout|pay|payment|receipt/, 'https://pay.netcoin.online'],
      [/merchant|pos|webhook|api key|refund|report/, 'https://merchant.netcoin.online'],
      [/listing readiness|real listing|exchange listing|exchange readiness/, 'https://exchange.netcoin.online/listing.html'],
      [/exchange|custody|reserve|withdrawal|deposit|hot wallet|cold wallet/, 'https://exchange.netcoin.online'],
      [/faucet|test coin/, 'https://faucet.netcoin.online'],
      [/community|discuss|idea|bounty|roadmap/, 'https://community.netcoin.online'],
      [/operator|runbook|incident|health center|ops|ledger audit|chainstate|peer advertise|maintenance/, 'https://operator.netcoin.online'],
      [/node|seed|peer|mining|status|network/, 'https://nodes.netcoin.online'],
      [/download|install|windows|mac|linux/, 'https://download.netcoin.online'],
      [/learn|guide|how/, 'https://learn.netcoin.online'],
      [/developer console|payment link|api key|webhook|reward simulation/, 'https://developers.netcoin.online/console.html'],
      [/localnet|local testnet|launch local|copyable command/, 'https://docs.netcoin.online/localnet.html'],
      [/availability|available now|feature status|test coverage/, 'https://features.netcoin.online'],
      [/api|developer|sdk|endpoint/, 'https://api.netcoin.online'],
      [/security|audit|checksum|release|verify|bug/, 'https://security.netcoin.online'],
      [/governance|proposal|treasury|vote|nip/, 'https://governance.netcoin.online'],
      [/market|prediction|lab|phase 7|poll/, 'https://markets.netcoin.online'],
      [/mempool|pending tx|unconfirmed/, 'https://explorer.netcoin.online/mempool.html']
    ];
    for (const [rx, u] of routes) {
      if (rx.test(l)) { location.href = u.indexOf('mempool.html') !== -1 ? u + '?q=' + encodeURIComponent(s) : u; return; }
    }
    // No keyword match and not a recognizable chain-data shape: fall back
    // to the explorer's own search box via its address lookup, since that's
    // the only page that will actually try to resolve an arbitrary string.
    location.href = 'https://explorer.netcoin.online/#/address/' + encodeURIComponent(s);
  }

  function buildGithubQuickstart() {
    if (q('[data-github-quickstart]')) return;
    const footer = q('.footer');
    if (!footer) return;
    const section = document.createElement('section');
    section.className = 'github-quickstart card';
    section.dataset.githubQuickstart = '';
    section.innerHTML = '<details><summary>Local setup</summary>' +
      '<div class="github-quickstart-grid">' +
      '<div><h2>Install</h2><pre>git clone https://github.com/netcoin-crl/netcoin.git\ncd netcoin\npython3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -e .</pre></div>' +
      '<div><h2>Wallet and mining</h2><pre>python -m netcoin wallet-new --out my-wallet.json --mnemonic\npython -m netcoin miner --node https://api.netcoin.online/api --wallet my-wallet.json --blocks 0 --sync-after\npython tools/check_public_network.py</pre></div>' +
      '<p class="muted github-quickstart-note">Use <code>https://api.netcoin.online/api</code> first. If your network blocks it, use <code>http://18.220.89.128/api</code>. Public-testnet coins have no real-money value.</p>' +
      '</div></details>';
    footer.insertAdjacentElement('beforebegin', section);
  }

  function closeFloatingPanelsOnOutside() {
    document.addEventListener('click', (ev) => {
      qa('.site-nav-group[open], .site-tools-more[open], .site-more[open]').forEach((d) => {
        if (!d.contains(ev.target)) d.removeAttribute('open');
      });
    });
  }

  window.NetCoinSite = { links, modes, routeSearch };
  applyViewLevel();
  normalizeNav();
  buildTools();
  syncModeUi();
  wireSettings();
  buildGithubQuickstart();
  buildViewToggle();
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


/* NetCoin v0.42 clarity layer: compact navigation, short copy, alerts, notes, and surface trust panels. */
(function () {
  'use strict';
  var NOTIFY_KEY = 'nc.notifications.v1';
  var MODE_KEY = 'nc.completionMode.v1';
  var paletteReturnFocus = null;
  var notificationReturnFocus = null;
  function qs(s, r) { return (r || document).querySelector(s); }
  function qsa(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function hostKey() {
    var bodySite = document.body && document.body.getAttribute('data-site');
    if (bodySite) return bodySite;
    var pathMatch = String(location.pathname || '').match(/\/sites\/([^\/]+)/);
    if (pathMatch && pathMatch[1]) return pathMatch[1];
    var host = (location.hostname || 'netcoin.online').replace(/^www\./,'').split('.')[0] || 'home';
    return (host === '127' || host === 'localhost' || host === '0') ? 'home' : host;
  }
  function shellRoot() { return qs('.shell') || qs('.wrap') || document.body; }
  function readJson(key, fallback) { try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch (e) { return fallback; } }
  function writeJson(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {} }
  function addNotification(title, detail, level) {
    var list = readJson(NOTIFY_KEY, []);
    list.unshift({ title: title, detail: detail, level: level || 'Healthy', at: new Date().toISOString(), page: hostKey() });
    writeJson(NOTIFY_KEY, list.slice(0, 30));
    updateNotifyButton();
  }
  function commandLinks() {
    var base = [
      ['Wallet','https://wallet.netcoin.online','send, receive, backup, fees, RBF, PSBT','User'],
      ['Explorer','https://explorer.netcoin.online','address, UTXOs, tx risk, mempool','User'],
      ['Markets','https://markets.netcoin.online','orderbook, trades, settlement','Trader'],
      ['Faucet','https://faucet.netcoin.online','claim, challenge, status','User'],
      ['Community','https://community.netcoin.online','posts, bounties, moderation','User'],
      ['Exchange','https://exchange.netcoin.online','deposits, withdrawals, custody','Operator'],
      ['Listing Readiness','https://exchange.netcoin.online/listing.html','code-side exchange checklist','Operator'],
      ['Operator','https://operator.netcoin.online','ledger audit, chainstate, peer health','Operator'],
      ['Verify release','https://download.netcoin.online/verify.html','checksums and signatures','Developer'],
      ['Developer Console','https://developers.netcoin.online/console.html','payment links, API keys, webhooks','Developer'],
      ['API','https://api.netcoin.online','OpenAPI contract','Developer'],
      ['Localnet','https://docs.netcoin.online/localnet.html','copyable testnet launch commands','Developer'],
      ['Feature status','https://features.netcoin.online','availability labels and test coverage','Developer'],
      ['Architecture','https://architecture.netcoin.online','Rust, TS, Python lanes','Developer']
    ];
    return base.map(function(row){ return { label: row[0], href: row[1], detail: row[2], mode: row[3] }; });
  }
  function buildSkipLink() {
    if (qs('.nc-skip-link')) return;
    var main = qs('main') || qs('.wrap') || qs('.shell') || document.body;
    if (!main.id) main.id = 'netcoin-main';
    if (!main.getAttribute('tabindex')) main.setAttribute('tabindex', '-1');
    var link = document.createElement('a');
    link.className = 'nc-skip-link';
    link.href = '#' + main.id;
    link.textContent = 'Skip to main content';
    document.body.insertBefore(link, document.body.firstChild);
  }

  function buildReadinessBanner() {
    if (qs('[data-nc-readiness-banner]')) return;
    var topbar = qs('.topbar');
    var root = shellRoot();
    if (!root) return;
    var banner = document.createElement('section');
    banner.className = 'nc-readiness-banner';
    banner.dataset.ncReadinessBanner = '';
    banner.innerHTML = '<strong>Public testnet.</strong><span>NET has no real-money value. Availability labels are not production claims.</span><a href="https://features.netcoin.online">Feature status</a>';
    if (topbar && topbar.parentNode) topbar.insertAdjacentElement('afterend', banner);
    else root.insertBefore(banner, root.firstChild);
  }

  function buildCommandPalette() {
    if (qs('#ncCommandPalette')) return;
    var panel = document.createElement('div');
    panel.id = 'ncCommandPalette';
    panel.className = 'nc-command-palette';
    panel.setAttribute('role','dialog');
    panel.setAttribute('aria-modal','true');
    panel.setAttribute('aria-labelledby','ncCommandTitle');
    panel.setAttribute('aria-describedby','ncCommandHelp');
    panel.innerHTML = '<div class="nc-command-box"><div class="nc-command-head"><h2 id="ncCommandTitle">Jump to…</h2><button class="nc-close" type="button" data-nc-close="palette" aria-label="Close command palette">Close</button></div><input class="nc-command-input" type="search" placeholder="Wallet, txid, market, docs…" aria-label="Search NetCoin" aria-controls="ncCommandResults" aria-describedby="ncCommandHelp"><div id="ncCommandResults" class="nc-command-results" role="listbox" aria-label="Command results"></div><p id="ncCommandHelp" class="muted">Ctrl/⌘ K opens this. Escape closes it.</p></div>';
    document.body.appendChild(panel);
    var input = qs('.nc-command-input', panel);
    var results = qs('.nc-command-results', panel);
    function render(filter) {
      var query = String(filter || '').trim().toLowerCase();
      var links = commandLinks().filter(function(item){ return !query || (item.label + ' ' + item.detail + ' ' + item.mode).toLowerCase().indexOf(query) !== -1; });
      if (query && /^([a-f0-9]{32,}|net[0-9a-z]+)/i.test(query)) {
        links.unshift({ label: 'Search pasted value in Explorer', href: 'https://explorer.netcoin.online?search=' + encodeURIComponent(filter), detail: 'Open address/transaction/block search', mode: 'User' });
      }
      results.innerHTML = links.map(function(item){ return '<a class="nc-command-item" role="option" href="'+esc(item.href)+'"><span><b>'+esc(item.label)+'</b><small>'+esc(item.detail)+'</small></span><small>'+esc(item.mode)+'</small></a>'; }).join('') || '<div class="nc-notice-item" role="status"><strong>No match</strong><small>Try wallet, explorer, market, faucet, or docs.</small></div>';
    }
    input.addEventListener('input', function(){ render(input.value); });
    render('');
  }
  function openPalette() {
    buildCommandPalette();
    var p = qs('#ncCommandPalette');
    if (!p) return;
    paletteReturnFocus = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
    p.classList.add('open');
    var input = qs('#ncCommandPalette .nc-command-input');
    if (input) { input.focus(); input.select(); }
  }
  function closePalette() {
    var p = qs('#ncCommandPalette');
    if (p) p.classList.remove('open');
    if (paletteReturnFocus && paletteReturnFocus.focus) paletteReturnFocus.focus();
    paletteReturnFocus = null;
  }
  function buildNotificationCenter() {
    if (qs('#ncNotificationCenter')) return;
    var panel = document.createElement('div');
    panel.id = 'ncNotificationCenter';
    panel.className = 'nc-notification-center';
    panel.setAttribute('role','dialog');
    panel.setAttribute('aria-modal','true');
    panel.setAttribute('aria-labelledby','ncNotificationTitle');
    panel.setAttribute('aria-describedby','ncNotificationHelp');
    panel.innerHTML = '<div class="nc-notification-box"><div class="nc-notification-head"><h2 id="ncNotificationTitle">Alerts</h2><button class="nc-close" type="button" data-nc-close="notifications" aria-label="Close alerts">Close</button></div><div class="nc-notification-list" role="log" aria-live="polite" aria-relevant="additions text"></div><div id="ncNotificationHelp" class="nc-next-step"><b>Local only.</b> Saved in this browser.</div></div>';
    document.body.appendChild(panel);
  }
  function renderNotifications() {
    buildNotificationCenter();
    var list = readJson(NOTIFY_KEY, []);
    var box = qs('#ncNotificationCenter .nc-notification-list');
    if (!box) return;
    box.innerHTML = (list.length ? list : [{title:'No notifications yet', detail:'Notes, previews, and proof checks appear here.', level:'Healthy', at:new Date().toISOString(), page:'global'}]).map(function(item){
      return '<div class="nc-notice-item"><span class="nc-status-badge '+(String(item.level).toLowerCase())+'">'+esc(item.level)+'</span><strong>'+esc(item.title)+'</strong><small>'+esc(item.detail)+' · '+esc(item.page)+' · '+esc(new Date(item.at).toLocaleString())+'</small></div>';
    }).join('');
  }
  function updateNotifyButton(){ var b=qs('#ncNotifyButton'); if(b){ var n=readJson(NOTIFY_KEY, []).length; b.textContent='Alerts '+(n?'('+n+')':''); } }
  function openNotifications(){
    buildNotificationCenter();
    renderNotifications();
    notificationReturnFocus = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
    var p = qs('#ncNotificationCenter');
    if (p) p.classList.add('open');
    var close = qs('#ncNotificationCenter [data-nc-close="notifications"]');
    if (close) close.focus();
  }
  function closeNotifications(){
    var p=qs('#ncNotificationCenter');
    if(p) p.classList.remove('open');
    if (notificationReturnFocus && notificationReturnFocus.focus) notificationReturnFocus.focus();
    notificationReturnFocus = null;
  }
  function buildNotifyButton(){ if(qs('#ncNotifyButton')) return; var b=document.createElement('button'); b.id='ncNotifyButton'; b.className='nc-notify-button'; b.type='button'; b.setAttribute('aria-haspopup','dialog'); b.setAttribute('aria-controls','ncNotificationCenter'); b.setAttribute('aria-label','Open local alerts'); b.textContent='Alerts'; document.body.appendChild(b); updateNotifyButton(); }
  function trapFloatingFocus(panel, ev) {
    if (!panel || !panel.classList.contains('open') || ev.key !== 'Tab') return;
    var focusable = qsa('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])', panel).filter(function(el){ return el.offsetParent !== null || el === document.activeElement; });
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
  }
  function wireGlobalEvents(){
    document.addEventListener('keydown', function(ev){
      trapFloatingFocus(qs('#ncCommandPalette'), ev);
      trapFloatingFocus(qs('#ncNotificationCenter'), ev);
      if ((ev.ctrlKey || ev.metaKey) && String(ev.key).toLowerCase()==='k') { ev.preventDefault(); openPalette(); }
      if(ev.key==='Escape'){ closePalette(); closeNotifications(); }
    });
    document.addEventListener('click', function(ev){ var t=ev.target; if(!t) return; if(t.id==='ncNotifyButton') openNotifications(); if(t.getAttribute && t.getAttribute('data-nc-close')==='palette') closePalette(); if(t.getAttribute && t.getAttribute('data-nc-close')==='notifications') closeNotifications(); if(t.id==='ncCommandPalette' && t===ev.target) closePalette(); if(t.id==='ncNotificationCenter' && t===ev.target) closeNotifications(); });
  }
  function guidedOnboarding(){
    if (readJson('nc.onboarding.v1', {}).dismissed) return;
    var surface = hostKey();
    if (!['netcoin','wallet','faucet','explorer'].includes(surface)) return;
    addNotification('Guided testnet path', 'Create wallet → backup → claim faucet NET → send test payment → verify in Explorer.', 'Healthy');
    writeJson('nc.onboarding.v1', { dismissed: true, at: new Date().toISOString() });
  }
  window.NetCoinProductCompletion = { buildCommandPalette: buildCommandPalette, buildNotificationCenter: buildNotificationCenter, addNotification: addNotification };
  buildSkipLink(); buildReadinessBanner(); buildCommandPalette(); buildNotificationCenter(); buildNotifyButton(); wireGlobalEvents();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', guidedOnboarding); else { guidedOnboarding(); }
})();
