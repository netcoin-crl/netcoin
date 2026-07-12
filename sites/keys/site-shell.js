(() => {
  'use strict';

  const MODE_KEY = 'nc.siteMode.v3';
  const modes = {
    user: {
      label: 'User',
      detail: 'Wallet, Explorer, Markets, Faucet.',
      groups: ['Core', 'Network', 'Community', 'Developers']
    },
    trader: {
      label: 'Trader',
      detail: 'Markets, portfolio, settlement.',
      groups: ['Core', 'Community', 'Network', 'Developers']
    },
    operator: {
      label: 'Operator',
      detail: 'Health, nodes, custody, releases.',
      groups: ['Network', 'Developers', 'Core', 'Community']
    },
    developer: {
      label: 'Developer',
      detail: 'Docs, API, design, downloads.',
      groups: ['Developers', 'Network', 'Core', 'Community']
    }
  };

  const links = [
    { href: 'https://wallet.netcoin.online', host: 'wallet.netcoin.online', label: 'Wallet', detail: 'send and receive', group: 'Core', primary: true },
    { href: 'https://explorer.netcoin.online', host: 'explorer.netcoin.online', label: 'Explorer', detail: 'verify activity', group: 'Core', primary: true },
    { href: 'https://markets.netcoin.online', host: 'markets.netcoin.online', label: 'Markets', detail: 'trade test markets', group: 'Core', primary: true },

    { href: 'https://netcoin.online', host: 'netcoin.online', label: 'Home', detail: 'testnet hub', group: 'Core' },
    { href: 'https://pay.netcoin.online', host: 'pay.netcoin.online', label: 'Pay', detail: 'links and receipts', group: 'Core' },
    { href: 'https://merchant.netcoin.online', host: 'merchant.netcoin.online', label: 'Merchant', detail: 'checkout', group: 'Core' },

    { href: 'https://faucet.netcoin.online', host: 'faucet.netcoin.online', label: 'Faucet', detail: 'claim NET', group: 'Network' },
    { href: 'https://nodes.netcoin.online', host: 'nodes.netcoin.online', label: 'Nodes', detail: 'seeds and mining', group: 'Network' },
    { href: 'https://status.netcoin.online', host: 'status.netcoin.online', label: 'Status', detail: 'health', group: 'Network' },
    { href: 'https://operator.netcoin.online', host: 'operator.netcoin.online', label: 'Operator', detail: 'ops health', group: 'Network' },
    { href: 'https://exchange.netcoin.online', host: 'exchange.netcoin.online', label: 'Exchange', detail: 'custody', group: 'Network' },
    { href: 'https://security.netcoin.online', host: 'security.netcoin.online', label: 'Security', detail: 'release safety', group: 'Network' },

    { href: 'https://community.netcoin.online', host: 'community.netcoin.online', label: 'Community', detail: 'posts and bounties', group: 'Community' },
    { href: 'https://governance.netcoin.online', host: 'governance.netcoin.online', label: 'Governance', detail: 'NIPs', group: 'Community' },
    { href: 'https://treasury.netcoin.online', host: 'treasury.netcoin.online', label: 'Treasury', detail: 'grants', group: 'Community' },
    { href: 'https://learn.netcoin.online', host: 'learn.netcoin.online', label: 'Learn', detail: 'guides', group: 'Community' },

    { href: 'https://docs.netcoin.online', host: 'docs.netcoin.online', label: 'Docs', detail: 'reference', group: 'Developers' },
    { href: 'https://api.netcoin.online', host: 'api.netcoin.online', label: 'API', detail: 'OpenAPI', group: 'Developers' },
    { href: 'https://developers.netcoin.online', host: 'developers.netcoin.online', label: 'SDKs', detail: 'SDKs', group: 'Developers' },
    { href: 'https://architecture.netcoin.online', host: 'architecture.netcoin.online', label: 'System Design', detail: 'architecture', group: 'Developers' },
    { href: 'https://features.netcoin.online', host: 'features.netcoin.online', label: 'Capabilities', detail: 'feature status', group: 'Developers' },
    { href: 'https://learn.netcoin.online#download', host: 'download.netcoin.online', label: 'Download', detail: 'install', group: 'Developers' },
    { href: 'https://download.netcoin.online/verify.html', host: 'download.netcoin.online', label: 'Verify Release', detail: 'verify files', group: 'Developers' }
  ];

  const featureGroups = [
    {
      title: 'Core',
      items: [
        ['Wallet', 'https://wallet.netcoin.online'],
        ['Explorer', 'https://explorer.netcoin.online'],
        ['Markets', 'https://markets.netcoin.online'],
        ['Pay', 'https://pay.netcoin.online'],
        ['Merchant', 'https://merchant.netcoin.online']
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
        ['Security', 'https://security.netcoin.online']
      ]
    },
    {
      title: 'Community',
      items: [
        ['Community', 'https://community.netcoin.online'],
        ['Ideas', 'https://community.netcoin.online#ideas'],
        ['Bounties', 'https://community.netcoin.online#bounties'],
        ['Governance', 'https://governance.netcoin.online'],
        ['Treasury', 'https://treasury.netcoin.online'],
        ['Learn', 'https://learn.netcoin.online']
      ]
    },
    {
      title: 'Developers',
      items: [
        ['Docs', 'https://docs.netcoin.online'],
        ['API', 'https://api.netcoin.online'],
        ['SDKs', 'https://developers.netcoin.online'],
        ['System Design', 'https://architecture.netcoin.online'],
        ['Capabilities', 'https://features.netcoin.online'],
        ['Download', 'https://learn.netcoin.online#download'],
        ['Verify Release', 'https://download.netcoin.online/verify.html']
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
        '<span>' + link.label + '</span><small>' + link.detail + '</small></a>';
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
      '<p class="site-settings-note">Reorders grouped secondary tools. Core navigation stays focused.</p>' +
      '</div></details>';
  }

  function normalizeNav() {
    const nav = q('.site-nav');
    if (!nav) return;
    const primary = links.filter((link) => link.primary);
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
      '<details class="site-tools-more"><summary>More</summary><div class="site-more-panel site-tools-more-panel">' + directoryHtml() + '</div></details>' +
      settingsHtml();
  }

  function buildTools() {
    const nav = q('.site-nav');
    if (!nav || q('.site-tools')) return;
    const tools = document.createElement('div');
    tools.className = 'site-tools';
    tools.innerHTML = '<div class="site-context"><span>Wallet-first</span><strong data-site-mode-label>' + modes[activeMode].label + '</strong><small data-site-mode-copy>' + modes[activeMode].detail + '</small></div><form class="site-search" role="search"><input type="search" aria-label="Search addresses, transactions, markets, or docs" placeholder="Search address, tx, market, or docs…"><button type="submit" aria-label="Search">Go</button></form>';
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
    const select = q('#netcoinSiteMode');
    if (!select) return;
    select.addEventListener('change', () => {
      const next = validMode(select.value) || 'user';
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
      [/feature|rating|score|catalog|all tools|directory/, 'https://features.netcoin.online'],
      [/wallet|private key|seed phrase|backup|send|receive|contact/, 'https://wallet.netcoin.online'],
      [/start|basic|beginner|home|community basic|pay basic/, 'https://netcoin.online'],
      [/invoice|checkout|pay|payment|receipt/, 'https://pay.netcoin.online'],
      [/merchant|pos|webhook|api key|refund|report/, 'https://merchant.netcoin.online'],
      [/exchange|custody|reserve|withdrawal|deposit|hot wallet|cold wallet/, 'https://exchange.netcoin.online'],
      [/faucet|test coin/, 'https://faucet.netcoin.online'],
      [/community|discuss|idea|bounty|roadmap/, 'https://community.netcoin.online'],
      [/operator|runbook|incident|health center|ops/, 'https://operator.netcoin.online'],
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


/* NetCoin v0.42 clarity layer: compact navigation, short copy, alerts, notes, and surface trust panels. */
(function () {
  'use strict';
  var NOTE_KEY = 'nc.localNotes.v1';
  var NOTIFY_KEY = 'nc.notifications.v1';
  var MODE_KEY = 'nc.completionMode.v1';
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
      ['Wallet','https://wallet.netcoin.online','send, receive, backup','User'],
      ['Explorer','https://explorer.netcoin.online','address, tx, block, mempool','User'],
      ['Markets','https://markets.netcoin.online','orderbook, trades, settlement','Trader'],
      ['Faucet','https://faucet.netcoin.online','claim, challenge, status','User'],
      ['Community','https://community.netcoin.online','posts, bounties, moderation','User'],
      ['Exchange','https://exchange.netcoin.online','deposits, withdrawals, custody','Operator'],
      ['Operator','https://operator.netcoin.online','health, diagnostics, bundle, alerts','Operator'],
      ['Verify release','https://download.netcoin.online/verify.html','checksums and signatures','Developer'],
      ['API','https://api.netcoin.online','OpenAPI contract','Developer'],
      ['Architecture','https://architecture.netcoin.online','Rust, TS, Python lanes','Developer']
    ];
    return base.map(function(row){ return { label: row[0], href: row[1], detail: row[2], mode: row[3] }; });
  }
  function buildCommandPalette() {
    if (qs('#ncCommandPalette')) return;
    var panel = document.createElement('div');
    panel.id = 'ncCommandPalette';
    panel.className = 'nc-command-palette';
    panel.setAttribute('role','dialog');
    panel.setAttribute('aria-modal','true');
    panel.innerHTML = '<div class="nc-command-box"><div class="nc-command-head"><h2>Jump to…</h2><button class="nc-close" type="button" data-nc-close="palette">Close</button></div><input class="nc-command-input" type="search" placeholder="Wallet, txid, market, docs…" aria-label="Search NetCoin"><div class="nc-command-results"></div><p class="muted">Ctrl/⌘ K opens this.</p></div>';
    document.body.appendChild(panel);
    var input = qs('.nc-command-input', panel);
    var results = qs('.nc-command-results', panel);
    function render(filter) {
      var query = String(filter || '').trim().toLowerCase();
      var links = commandLinks().filter(function(item){ return !query || (item.label + ' ' + item.detail + ' ' + item.mode).toLowerCase().indexOf(query) !== -1; });
      if (query && /^([a-f0-9]{32,}|net[0-9a-z]+)/i.test(query)) {
        links.unshift({ label: 'Search pasted value in Explorer', href: 'https://explorer.netcoin.online?search=' + encodeURIComponent(filter), detail: 'Open address/transaction/block search', mode: 'User' });
      }
      results.innerHTML = links.map(function(item){ return '<a class="nc-command-item" href="'+esc(item.href)+'"><span><b>'+esc(item.label)+'</b><small>'+esc(item.detail)+'</small></span><small>'+esc(item.mode)+'</small></a>'; }).join('') || '<div class="nc-notice-item"><strong>No match</strong><small>Try wallet, explorer, market, faucet, or docs.</small></div>';
    }
    input.addEventListener('input', function(){ render(input.value); });
    render('');
  }
  function openPalette() { buildCommandPalette(); qs('#ncCommandPalette').classList.add('open'); var input = qs('#ncCommandPalette .nc-command-input'); if (input) { input.focus(); input.select(); } }
  function closePalette() { var p = qs('#ncCommandPalette'); if (p) p.classList.remove('open'); }
  function buildNotificationCenter() {
    if (qs('#ncNotificationCenter')) return;
    var panel = document.createElement('div');
    panel.id = 'ncNotificationCenter';
    panel.className = 'nc-notification-center';
    panel.setAttribute('role','dialog');
    panel.setAttribute('aria-modal','true');
    panel.innerHTML = '<div class="nc-notification-box"><div class="nc-notification-head"><h2>Alerts</h2><button class="nc-close" type="button" data-nc-close="notifications">Close</button></div><div class="nc-notification-list"></div><div class="nc-next-step"><b>Local only.</b> Saved in this browser.</div></div>';
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
  function openNotifications(){ buildNotificationCenter(); renderNotifications(); qs('#ncNotificationCenter').classList.add('open'); }
  function closeNotifications(){ var p=qs('#ncNotificationCenter'); if(p) p.classList.remove('open'); }
  function recordLocalNote(surface, text) {
    var notes = readJson(NOTE_KEY, {});
    var key = surface || hostKey();
    notes[key] = notes[key] || [];
    notes[key].unshift({ text: String(text || '').trim(), at: new Date().toISOString(), url: location.href });
    notes[key] = notes[key].filter(function(n){ return n.text; }).slice(0, 20);
    writeJson(NOTE_KEY, notes);
    addNotification('Local note saved', 'Saved for '+key+'. Local only.', 'Healthy');
  }
  function localNoteHtml(surface) {
    var notes = readJson(NOTE_KEY, {}); var items = notes[surface] || [];
    return '<div class="nc-local-note"><h3>Notes</h3><p class="muted">Private browser notes for labels, contacts, or reminders.</p><textarea data-nc-note-input placeholder="Add note…"></textarea><button type="button" class="nc-icon-button" data-nc-save-note="'+esc(surface)+'">Save</button><div data-nc-note-list>'+items.map(function(n){ return '<div class="nc-notice-item"><strong>'+esc(n.text)+'</strong><small>'+esc(new Date(n.at).toLocaleString())+'</small></div>'; }).join('')+'</div></div>';
  }
  function timeline(items) { return '<div class="nc-timeline">'+items.map(function(item,i){ return '<div class="nc-step"><div class="nc-step-dot">'+(i+1)+'</div><div><b>'+esc(item[0])+'</b><small>'+esc(item[1])+'</small></div></div>'; }).join('')+'</div>'; }
  function statusStrip(items) { return '<div class="nc-trust-strip">'+items.map(function(item){ return '<span class="nc-status-badge '+esc(item[1])+'">'+esc(item[0])+'</span>'; }).join('')+'</div>'; }
  function card(title, copy){ return '<div class="nc-upgrade-card"><b>'+esc(title)+'</b><p>'+esc(copy)+'</p></div>'; }
  function panel(title, intro, body){ return '<section class="nc-upgrade-panel nc-ui-v042" data-nc-completion-panel><h2>'+esc(title)+'</h2><p class="muted">'+esc(intro)+'</p>'+body+'</section>'; }
  function walletPanel(){
    return panel('Wallet safety','Back up first. Review before send. Verify in Explorer.',
      statusStrip([['Fresh','healthy'],['Local labels','healthy'],['Backup first','warning']])+
      '<div class="nc-upgrade-grid">'+
      card('Overview, Send, Receive, and Activity','Simple mode keeps the daily wallet path visible.')+
      card('Security Center','Lock state, backup status, and signing readiness.')+
      card('Review before broadcast','Check amount, fee, destination, and risk.')+
      card('Recovery drill','Practice restore before storing serious test funds.')+
      '</div>'+timeline([['Prepare','Recipient, amount, fee.'],['Review','Confirm cost and destination.'],['Sign','Browser, offline, or hardware-ready path.'],['Verify','Open Explorer and label it.']])+localNoteHtml('wallet')+
      '<div class="nc-next-step"><b>Next:</b> verify backup, then send a tiny test payment.</div>');
  }
  function explorerPanel(){
    return panel('Explorer trust','Show status first. Keep raw data available, not dominant.',
      statusStrip([['Verified','healthy'],['Active chain','healthy'],['Reorg-aware','warning']])+
      '<div class="nc-upgrade-grid">'+card('Address, tx, block, mempool','Each page starts with a plain summary.')+card('Confirmation badges','Pending, confirmed, reorg-risk, orphaned, invalid.')+card('Fee bands','Mempool age and fee buckets guide wallet fees.')+card('CSV exports','Include schema, range, height, and source.')+'</div>'+localNoteHtml('explorer'));
  }
  function marketsPanel(){
    return panel('Markets risk','Preview orderbook depth, trades, portfolio impact, cost, fee, max loss, and settlement before action.',
      '<div class="nc-mode-switch" data-nc-market-mode><button class="active" type="button" data-mode="simple">Simple</button><button type="button" data-mode="advanced">Advanced</button></div>'+statusStrip([['Lifecycle','healthy'],['Risk preview','warning'],['Settlement','healthy']])+
      '<div class="nc-form-grid"><label>Stake NET<input data-nc-market-stake inputmode="decimal" value="10"></label><label>Price %<input data-nc-market-price inputmode="decimal" value="62"></label><label>Fee %<input data-nc-market-fee inputmode="decimal" value="1"></label></div><div class="nc-upgrade-card" data-nc-market-preview></div>'+timeline([['Preview','Cost, fee, max loss, payout.'],['Submit','Confirm market state.'],['Portfolio','Split realized and unrealized PnL.'],['Settlement','Show evidence and dispute path.']])+localNoteHtml('markets'));
  }
  function faucetPanel(){
    return panel('Faucet clarity','Show challenge, claim, status, admin state, and recovery without extra copy.',
      statusStrip([['Funding visible','healthy'],['Provider credentials pending','warning'],['Recovery copy','healthy']])+timeline([['Eligible','Cooldown, cap, funding.'],['Challenge','PoW or CAPTCHA.'],['Claim','Broadcast payment.'],['Cooldown','Show next claim time.']])+'<div class="nc-upgrade-grid">'+card('Provider status','Turnstile/hCaptcha when configured.')+card('Admin audit','Pause, cap, and difficulty changes are logged.')+'</div>');
  }
  function communityPanel(){
    return panel('Community quality','Less noise. Clear profiles, moderation, bounties, and reputation.',
      '<div class="nc-upgrade-grid">'+card('Profile basics','Name, local identity, contributions, badges.')+card('Moderation audit','Reports and actions stay reviewable.')+card('Bounty lifecycle','Proposed → accepted → submitted → paid.')+card('Anti-spam limits','Explain limits without exposing rules.')+'</div>');
  }
  function exchangePanel(){
    return panel('Custody safety','Make deposits, withdrawals, custody, reserves, and approvals visible.',
      statusStrip([['Custody scaffold','warning'],['Audit trail','warning'],['Reserves visible','healthy']])+'<div class="nc-upgrade-grid">'+card('Custody risk','Hot balance, cold reserve, limits, approvals.')+card('Withdrawals','Requested → approved → signed → confirmed.')+card('Cold signing','Checklist before cold-to-hot movement.')+card('Ledger checks','Imbalance blocks readiness.')+'</div>'+timeline([['Deposit','Watch confirmations.'],['Credit','Apply policy.'],['Withdraw','Run checks and approvals.'],['Broadcast','Track confirmation.']]) );
  }
  function operatorPanel(){
    return panel('Operator center','Health alerts, diagnostics bundle, runbooks, release blockers, and proof evidence in one place.',
      statusStrip([['Health grouped','healthy'],['Blockers visible','warning'],['Diagnostics preview','healthy']])+'<div class="nc-upgrade-grid">'+card('Release blockers','Python, Rust, TS, browser, accessibility, security.')+card('Runbooks','Each alert links to the action.')+card('Diagnostics bundle','Preview data before export.')+card('Proof evidence','Logs and hashes grouped by gate.')+'</div>');
  }
  function securityPanel(){
    return panel('Security readiness','Show limitations, dependencies, fuzz targets, SBOM, provenance, and audit package.',
      statusStrip([['Limitations visible','healthy'],['External audit not claimed','warning'],['Signed release required','warning']])+'<div class="nc-upgrade-grid">'+card('Audit bundle','Spec, threat model, vectors, tests, deps.')+card('Fuzz matrix','Tx, block, script, wallet, mempool, markets.')+card('Dependency policy','Reproducible install and vulnerability review.')+card('Signed provenance','Checksums, signatures, SBOM, proof.')+'</div>');
  }
  function genericPanel(){ return panel('Product clarity','One job, one action, one trust signal, one next step.', statusStrip([['Healthy','healthy'],['No dead ends','healthy']])+'<div class="nc-upgrade-grid">'+card('Command palette','Ctrl/⌘ K opens Wallet, Explorer, Markets, Faucet, Operator, Docs.')+card('Alerts','Local-only status and reminders.')+card('Notes','Private labels and reminders.')+card('Status words','Healthy, Warning, Offline, Maintenance.')+'</div>'+localNoteHtml(hostKey())); }
  function surfaceHtml(surface) {
    if (surface === 'wallet') return walletPanel();
    if (surface === 'explorer') return explorerPanel();
    if (surface === 'markets') return marketsPanel();
    if (surface === 'faucet') return faucetPanel();
    if (surface === 'community' || surface === 'governance' || surface === 'treasury') return communityPanel();
    if (surface === 'exchange') return exchangePanel();
    if (surface === 'operator' || surface === 'status' || surface === 'nodes') return operatorPanel();
    if (surface === 'security' || surface === 'download') return securityPanel();
    return genericPanel();
  }
  function mountSurfaceCompletion() {
    if (qs('[data-nc-completion-panel]')) return;
    var root = shellRoot();
    var html = surfaceHtml(hostKey());
    var wrap = document.createElement('div'); wrap.innerHTML = html;
    var target = qs('.footer', root) || root.lastElementChild;
    if (target && target.parentNode === root) root.insertBefore(wrap.firstElementChild, target); else root.appendChild(wrap.firstElementChild);
    wireCompletionControls();
  }
  function buildNotifyButton(){ if(qs('#ncNotifyButton')) return; var b=document.createElement('button'); b.id='ncNotifyButton'; b.className='nc-notify-button'; b.type='button'; b.textContent='Alerts'; document.body.appendChild(b); updateNotifyButton(); }
  function wireCompletionControls(){
    qsa('[data-nc-save-note]').forEach(function(btn){ if(btn.dataset.wired) return; btn.dataset.wired='1'; btn.addEventListener('click', function(){ var area = btn.parentNode.querySelector('[data-nc-note-input]'); recordLocalNote(btn.getAttribute('data-nc-save-note'), area ? area.value : ''); if(area) area.value=''; }); });
    var preview = qs('[data-nc-market-preview]');
    function calcPreview(){ if(!preview) return; var stake=parseFloat((qs('[data-nc-market-stake]')||{}).value||'0'); var price=parseFloat((qs('[data-nc-market-price]')||{}).value||'0'); var fee=parseFloat((qs('[data-nc-market-fee]')||{}).value||'0'); var feeNet=stake*(fee/100); var payout=price>0?stake/(price/100):0; preview.innerHTML='<b>Order preview</b><div class="nc-kv"><span>You pay</span><strong>'+stake.toFixed(2)+' NET</strong><span>Fee before submit</span><strong>'+feeNet.toFixed(4)+' NET</strong><span>Max loss</span><strong>'+stake.toFixed(2)+' NET</strong><span>Potential payout</span><strong>'+payout.toFixed(2)+' NET</strong></div>'; }
    qsa('[data-nc-market-stake],[data-nc-market-price],[data-nc-market-fee]').forEach(function(el){ el.addEventListener('input', calcPreview); }); calcPreview();
    qsa('[data-nc-market-mode] button').forEach(function(btn){ btn.addEventListener('click', function(){ qsa('[data-nc-market-mode] button').forEach(function(b){b.classList.remove('active')}); btn.classList.add('active'); addNotification('Market mode changed', 'Switched to '+btn.getAttribute('data-mode')+' market controls.', 'Healthy'); }); });
  }
  function wireGlobalEvents(){
    document.addEventListener('keydown', function(ev){ if ((ev.ctrlKey || ev.metaKey) && String(ev.key).toLowerCase()==='k') { ev.preventDefault(); openPalette(); } if(ev.key==='Escape'){ closePalette(); closeNotifications(); } });
    document.addEventListener('click', function(ev){ var t=ev.target; if(!t) return; if(t.id==='ncNotifyButton') openNotifications(); if(t.getAttribute && t.getAttribute('data-nc-close')==='palette') closePalette(); if(t.getAttribute && t.getAttribute('data-nc-close')==='notifications') closeNotifications(); if(t.id==='ncCommandPalette' && t===ev.target) closePalette(); if(t.id==='ncNotificationCenter' && t===ev.target) closeNotifications(); });
  }
  function guidedOnboarding(){
    if (readJson('nc.onboarding.v1', {}).dismissed) return;
    var surface = hostKey();
    if (!['netcoin','wallet','faucet','explorer'].includes(surface)) return;
    addNotification('Guided testnet path', 'Create wallet → backup → claim faucet NET → send test payment → verify in Explorer.', 'Healthy');
    writeJson('nc.onboarding.v1', { dismissed: true, at: new Date().toISOString() });
  }
  window.NetCoinProductCompletion = { buildCommandPalette: buildCommandPalette, buildNotificationCenter: buildNotificationCenter, mountSurfaceCompletion: mountSurfaceCompletion, recordLocalNote: recordLocalNote, addNotification: addNotification };
  buildCommandPalette(); buildNotificationCenter(); buildNotifyButton(); wireGlobalEvents();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ mountSurfaceCompletion(); guidedOnboarding(); }); else { mountSurfaceCompletion(); guidedOnboarding(); }
})();
