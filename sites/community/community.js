'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let activePostSort = 'hot';
let activeCommentPost = '';

// --- Inline image support -------------------------------------------------
// This project has no object storage/CDN, so images are downscaled/compressed
// client-side and submitted as base64 data URIs (server enforces a ~300KB cap).
const IMAGE_MAX_DIM = 1200;
const IMAGE_MAX_BYTES = 290 * 1024; // stay comfortably under the server's 300KB cap
const imageState = {}; // key -> data URI (or '' when cleared)

function readFileAsDataUri(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Could not read file'));
    reader.readAsDataURL(file);
  });
}
function loadImageEl(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not decode image'));
    img.src = src;
  });
}
async function compressImageFile(file) {
  const raw = await readFileAsDataUri(file);
  const img = await loadImageEl(raw);
  let { width, height } = img;
  if (width > IMAGE_MAX_DIM || height > IMAGE_MAX_DIM) {
    const scale = IMAGE_MAX_DIM / Math.max(width, height);
    width = Math.max(1, Math.round(width * scale));
    height = Math.max(1, Math.round(height * scale));
  }
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0, width, height);
  let quality = 0.85;
  let out = canvas.toDataURL('image/jpeg', quality);
  while (out.length * 0.75 > IMAGE_MAX_BYTES && quality > 0.3) {
    quality -= 0.1;
    out = canvas.toDataURL('image/jpeg', quality);
  }
  if (out.length * 0.75 > IMAGE_MAX_BYTES) throw new Error('Image is too large even after compression');
  return out;
}
// Wires a file input + preview + clear button as a matched trio, keeping the
// resulting data URI in imageState[key] for the composer to read at submit time.
function wireImagePicker(key, inputSel, btnSel, previewWrapSel, previewImgSel, clearSel, resultSel) {
  const input = $(inputSel);
  const btn = $(btnSel);
  const wrap = $(previewWrapSel);
  const img = $(previewImgSel);
  const clearBtn = $(clearSel);
  if (!input || !btn || !wrap || !img || !clearBtn) return;
  btn.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    try {
      const dataUri = await compressImageFile(file);
      imageState[key] = dataUri;
      img.src = dataUri;
      wrap.classList.remove('hide');
    } catch (e) {
      setToast(resultSel, e.message, 'err');
    } finally {
      input.value = '';
    }
  });
  clearBtn.addEventListener('click', () => {
    imageState[key] = '';
    img.src = '';
    wrap.classList.add('hide');
  });
}
function takeImage(key) {
  const v = imageState[key] || '';
  imageState[key] = '';
  return v;
}
function resetImagePreview(previewWrapSel, previewImgSel) {
  const wrap = $(previewWrapSel);
  const img = $(previewImgSel);
  if (wrap) wrap.classList.add('hide');
  if (img) img.src = '';
}
function postMediaHtml(imageUri, cls = 'post-image') {
  if (!imageUri) return '';
  return `<div class="${cls}"><img src="${esc(imageUri)}" data-lightbox-src="${esc(imageUri)}" alt="attached image" loading="lazy" /></div>`;
}
function openLightbox(src) {
  let box = $('#imageLightbox');
  if (!box) {
    box = document.createElement('div');
    box.id = 'imageLightbox';
    box.className = 'lightbox hide';
    box.innerHTML = '<button type="button" class="lightbox-close" aria-label="Close">&times;</button><img alt="expanded image" />';
    document.body.appendChild(box);
    box.addEventListener('click', (ev) => { if (ev.target === box || ev.target.closest('.lightbox-close')) closeLightbox(); });
    document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeLightbox(); });
  }
  box.querySelector('img').src = src;
  box.classList.remove('hide');
}
function closeLightbox() {
  const box = $('#imageLightbox');
  if (box) box.classList.add('hide');
}
document.addEventListener('click', (ev) => {
  const target = ev.target.closest('[data-lightbox-src]');
  if (target) openLightbox(target.dataset.lightboxSrc);
});

async function api(path, options = {}) {
  const res = await fetch('/api' + path, options);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok || data.error) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}
function post(path, body) { return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
function setText(sel, value) { const el = $(sel); if (el) el.textContent = value; }
function setToast(sel, msg, cls = '') { const el = $(sel); if (!el) return; el.textContent = msg; el.className = 'toast ' + cls; }
function timeLabel(t) {
  const n = Number(t || Date.now() / 1000);
  const diff = Math.max(0, Date.now() / 1000 - n);
  if (diff < 60) return 'now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  try { return new Date(n * 1000).toLocaleDateString(); } catch { return String(t || ''); }
}
function shortId(id) { const s = String(id || ''); return s.length > 18 ? s.slice(0, 10) + '…' + s.slice(-6) : s; }
function amount(x) { const n = Number(x || 0); return Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 8 }) : esc(x); }
function openTab(name) {
  $$('.community-tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $$('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  if (history.replaceState) history.replaceState(null, '', '#' + name);
}
function redditCard({ postId = '', score = 0, title = '', body = '', meta = [], tag = '', commentCount = 0, actions = [], image = '' }) {
  const metaHtml = [tag ? `<span class="tag">${esc(tag)}</span>` : '', ...meta.map(esc)].filter(Boolean).map(x => x.startsWith('<') ? x : `<span>${x}</span>`).join('');
  const actionHtml = actions.map(a => a.html || `<button type="button" ${a.attr || ''}>${esc(a.label)}</button>`).join('');
  return `<article class="reddit-card" data-post-id="${esc(postId)}"><div class="vote-rail"><button type="button" data-vote-post="${esc(postId)}" data-direction="up" aria-label="upvote">▲</button><strong>${esc(score)}</strong><button type="button" data-vote-post="${esc(postId)}" data-direction="down" aria-label="downvote">▼</button></div><div class="post-body"><div class="post-meta">${metaHtml}</div><h3>${esc(title)}</h3><p>${esc(body)}</p>${postMediaHtml(image)}<div class="post-stats"><button type="button" data-open-comments="${esc(postId)}">${Number(commentCount || 0)} comments</button><span>${esc(postId)}</span></div>${actionHtml ? `<div class="post-actions">${actionHtml}</div>` : ''}</div></article>`;
}
function cardPost(p, opts = {}) {
  const actions = [{ html: `<button type="button" data-report-post="${esc(p.post_id || '')}">Report</button>` }];
  if (opts.canPin) {
    actions.push({ html: `<button type="button" data-pin-post="${esc(p.post_id || '')}" data-circle-id="${esc(opts.circleId || '')}">${opts.isPinned ? 'Unpin' : 'Pin'}</button>` });
  }
  return redditCard({
    postId: p.post_id || '',
    score: Number(p.score || p.votes || 0),
    title: (opts.isPinned ? '\u{1F4CC} ' : '') + (p.title || (p.category === 'help' ? 'Help request' : 'Community post')),
    body: p.message || '',
    tag: p.category || 'general',
    commentCount: p.comment_count || 0,
    image: p.image || '',
    meta: ['u/' + (p.name || p.author || 'Anonymous'), timeLabel(p.created_at), (p.sort ? 'sort:' + p.sort : '')].filter(Boolean),
    actions
  });
}
function cardIdea(i) {
  return redditCard({
    postId: i.idea_id || '',
    score: Number(i.votes || 0),
    title: i.title || 'Untitled idea',
    body: i.description || i.details || '',
    tag: i.category || 'idea',
    meta: ['u/' + (i.name || i.author || 'Anonymous'), timeLabel(i.created_at), i.status || 'open'],
    actions: [{ html: `<button type="button" data-vote-idea="${esc(i.idea_id || '')}">Vote</button>` }]
  });
}
function cardBounty(b) {
  return `<article class="bounty-card"><div class="bounty-meta"><span>${esc(b.status || 'open')}</span><span class="reward">${esc(b.reward || b.amount || '0')} NET</span></div><h3>${esc(b.title || b.bounty_id || 'Bounty')}</h3><p class="muted">${esc(b.description || 'No description yet.')}</p><div class="post-actions"><a href="https://explorer.netcoin.online#/community">Submit work</a></div></article>`;
}
function commentCard(c, depth = 0) {
  const indent = depth > 0 ? ` style="margin-left:${Math.min(depth, 6) * 20}px"` : '';
  return `<article class="comment-card reddit-comment" data-comment-id="${esc(c.comment_id || '')}"${indent}><div class="comment-meta"><b>u/${esc(c.name || 'Anonymous')}</b><span>${esc(timeLabel(c.created_at))}</span></div><p>${esc(c.message || '')}</p>${postMediaHtml(c.image || '', 'comment-image')}<div class="comment-actions"><button type="button" class="link-btn" data-reply-to="${esc(c.comment_id || '')}">Reply</button></div></article>`;
}
// Comments come back flat (post_id + optional parent_comment_id); build a
// reply tree client-side so nesting is just a display concern, not a
// separate storage/query shape on the server.
function renderCommentTree(comments) {
  const byParent = new Map();
  for (const c of comments) {
    const key = c.parent_comment_id || '';
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(c);
  }
  const walk = (parentId, depth) => (byParent.get(parentId) || [])
    .map((c) => commentCard(c, depth) + walk(c.comment_id, depth + 1)).join('');
  return walk('', 0);
}
function circleProgressHtml(c) {
  const members = (c.members || []).length;
  const threshold = c.activation_threshold || 5;
  const pct = Math.min(100, Math.round((members / threshold) * 100));
  return c.status === 'active'
    ? `<span class="tag ok">active</span>`
    : `<div class="circle-progress"><div class="circle-progress-bar" style="width:${pct}%"></div></div><span class="muted">${members}/${threshold} to activate</span>`;
}
function cardCircle(c) {
  return `<article class="reddit-card" data-post-id="${esc(c.circle_id || '')}"><div class="post-body"><div class="post-meta"><span class="tag">${esc(c.status || 'proposed')}</span><span>u/${esc(c.creator || 'Anonymous')}</span><span>${esc(timeLabel(c.created_at))}</span></div><h3><button type="button" class="link-btn" data-open-circle="${esc(c.circle_id || '')}">${esc(c.name || c.circle_id || 'Circle')}</button></h3><p>${esc(c.description || 'No description yet.')}</p>${circleProgressHtml(c)}<div class="post-actions"><button type="button" data-join-circle="${esc(c.circle_id || '')}">Join</button></div></div></article>`;
}
function modCard(item) {
  const r = item.report || {};
  const p = item.post || {};
  return `<article class="mod-card"><div class="post-meta"><span class="tag">${esc(r.status || 'open')}</span><span>${esc(r.report_id || '')}</span><span>${esc(timeLabel(r.created_at))}</span></div><h3>${esc(p.message ? p.message.slice(0, 90) : (r.post_id || 'Report'))}</h3><p>${esc(r.reason || '')}</p><div class="post-actions"><button type="button" data-mod-target="${esc(r.post_id || r.report_id || '')}" data-mod-action="hide">Hide post</button><button type="button" data-mod-target="${esc(r.post_id || r.report_id || '')}" data-mod-action="reviewed">Mark reviewed</button></div></article>`;
}
async function loadPosts() {
  const feed = $('#postFeed');
  try {
    const d = await api('/community/posts?limit=80&sort=' + encodeURIComponent(activePostSort));
    const posts = d.posts || [];
    setText('#postCount', d.count ?? posts.length);
    feed.innerHTML = posts.length ? posts.map(cardPost).join('') : '<div class="empty-state">No posts yet. Start the first thread.</div>';
  } catch (e) { feed.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
async function loadComments(postId) {
  const id = postId || activeCommentPost || $('#commentPostId')?.value || '';
  const out = $('#commentList');
  if (!id) { out.innerHTML = '<div class="empty-state">Pick a post from the feed (or paste a post ID above) to view its comments.</div>'; return; }
  activeCommentPost = id;
  $('#commentPostId').value = id;
  try {
    const d = await api('/community/posts/' + encodeURIComponent(id) + '/comments');
    out.innerHTML = (d.comments || []).length ? renderCommentTree(d.comments) : '<div class="empty-state">No comments yet. Be the first to reply.</div>';
  } catch (e) { out.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
async function loadIdeas() {
  const feed = $('#ideaFeed');
  try {
    const d = await api('/community/improvements');
    const ideas = d.improvements || [];
    setText('#ideaCount', d.count ?? ideas.length);
    feed.innerHTML = ideas.length ? ideas.map(cardIdea).join('') : '<div class="empty-state">No ideas yet. Suggest one.</div>';
  } catch (e) { feed.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
async function loadBounties() {
  const feed = $('#bountyFeed');
  try {
    const d = await api('/community/bounties');
    const bounties = d.bounties || [];
    const open = bounties.filter(b => (b.status || 'open') === 'open');
    setText('#bountyCount', open.length || bounties.length);
    feed.innerHTML = bounties.length ? bounties.map(cardBounty).join('') : '<div class="empty-state">No bounties yet.</div>';
  } catch (e) { feed.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
function leaderboardTable(title, rows) {
  const body = (rows || []).length ? rows.slice(0, 20).map((r, i) => `<tr><td class="rank">#${esc(r.rank || i + 1)}</td><td class="id" title="${esc(r.id || r.address || '')}">${esc(r.short_id || shortId(r.id || r.address || 'unknown'))}</td><td class="amount">${amount(r.amount ?? r.amount_sats)} NET</td></tr>`).join('') : '<tr><td colspan="3" class="muted">No data yet.</td></tr>';
  return `<section class="leaderboard-table"><h3>${esc(title)}</h3><table><thead><tr><th>Rank</th><th>Account</th><th class="amount">Amount</th></tr></thead><tbody>${body}</tbody></table></section>`;
}
let lastLeaderboardData = null;
let activeLeaderTab = 'top_miners';
const LEADER_TAB_TITLES = { top_miners: 'Top miners', top_earners: 'Top earners', top_donors: 'Top donors' };
function renderLeaderboardTab() {
  const out = $('#leaderboardsOut');
  const d = lastLeaderboardData;
  if (!d) return;
  out.innerHTML = leaderboardTable(LEADER_TAB_TITLES[activeLeaderTab], d[activeLeaderTab]);
  // Counts live on the tab buttons themselves (one horizontal row) instead of
  // a separate summary bar -- the summary used to sit as a sibling of the
  // table inside a CSS grid, so each count pill got stretched into its own
  // tall empty column at the table's height.
  const counts = d.summary
    ? { top_miners: d.summary.miner_count, top_earners: d.summary.earner_count, top_donors: d.summary.donor_count }
    : {};
  document.querySelectorAll('.leader-tab-count').forEach((el) => {
    const key = el.dataset.countFor;
    const n = counts[key];
    el.textContent = n == null ? '' : `(${n})`;
  });
}
async function loadLeaderboards() {
  const out = $('#leaderboardsOut');
  try {
    lastLeaderboardData = await api('/community/leaderboards');
    renderLeaderboardTab();
    const side = $('#sidebarLeaders');
    if (side) side.innerHTML = (lastLeaderboardData.top_miners || []).slice(0, 5).map((r, i) => `<div class="mini-leader"><span>#${i + 1} ${esc(r.short_id || shortId(r.id || 'unknown'))}</span><b>${amount(r.amount)} NET</b></div>`).join('') || '<p class="muted">No miners yet.</p>';
  } catch (e) { out.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
let allCircles = [];
function renderCircleFeed() {
  const feed = $('#circleFeed');
  const q = (($('#circleSearch') || {}).value || '').trim().toLowerCase();
  const filtered = q ? allCircles.filter((c) => (c.name || '').toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)) : allCircles;
  feed.innerHTML = filtered.length
    ? filtered.map(cardCircle).join('')
    : (allCircles.length ? '<div class="empty-state">No circles match that search.</div>' : '<div class="empty-state">No circles yet. Propose one.</div>');
}
async function loadCircles() {
  const feed = $('#circleFeed');
  try {
    const d = await api('/community/circles');
    allCircles = d.circles || [];
    renderCircleFeed();
  } catch (e) { feed.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
let activeCircleId = '';
async function loadCirclePosts(circleId) {
  const feed = $('#circlePostFeed');
  const pinnedBox = $('#circlePinnedPost');
  const c = allCircles.find((x) => x.circle_id === circleId) || {};
  const isCreator = ($('#circleCreator')?.value || '').trim() === c.creator;
  try {
    const d = await api('/community/posts?limit=80&circle_id=' + encodeURIComponent(circleId));
    const posts = d.posts || [];
    const pinnedId = c.pinned_post_id || '';
    const pinned = pinnedId ? posts.find((p) => p.post_id === pinnedId) : null;
    pinnedBox.innerHTML = pinned ? cardPost(pinned, { canPin: isCreator, circleId, isPinned: true }) : '';
    const rest = posts.filter((p) => p.post_id !== pinnedId);
    feed.innerHTML = rest.length
      ? rest.map((p) => cardPost(p, { canPin: isCreator, circleId, isPinned: false })).join('')
      : (pinned ? '' : '<div class="empty-state">No posts in this circle yet. Start the first thread.</div>');
  } catch (e) { feed.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
function openCircleDetail(circleId) {
  const c = allCircles.find((x) => x.circle_id === circleId);
  if (!c) return;
  activeCircleId = circleId;
  $('#circleBrowse').classList.add('hide');
  $('#circleDetail').classList.remove('hide');
  $('#circleDetailName').textContent = c.name || c.circle_id || 'Circle';
  $('#circleDetailDescription').textContent = c.description || 'No description yet.';
  const rulesBox = $('#circleDetailRules');
  if (c.rules) { rulesBox.classList.remove('hide'); $('#circleDetailRulesText').textContent = c.rules; }
  else { rulesBox.classList.add('hide'); }
  $('#circleDetailStatus').textContent = c.status || 'proposed';
  $('#circleDetailStatus').className = 'tag' + (c.status === 'active' ? ' ok' : '');
  $('#circleDetailProgress').innerHTML = circleProgressHtml(c);
  $('#circleDetailJoin').dataset.joinCircle = circleId;
  loadCirclePosts(circleId);
  if (history.replaceState) history.replaceState(null, '', '#circles/' + encodeURIComponent(circleId));
}
function backToCircles() {
  activeCircleId = '';
  $('#circleDetail').classList.add('hide');
  $('#circleBrowse').classList.remove('hide');
  if (history.replaceState) history.replaceState(null, '', '#circles');
}
async function loadModQueue() {
  const out = $('#modQueue');
  try {
    const d = await api('/community/moderation');
    out.innerHTML = (d.queue || []).length ? d.queue.map(modCard).join('') : '<p class="muted">No open reports.</p>';
  } catch (e) { out.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}
async function boot() {
  const initial = (location.hash || '#posts').slice(1);
  const circleMatch = initial.match(/^circles\/(.+)$/);
  if (circleMatch) openTab('circles');
  else if (['posts', 'comments', 'ideas', 'bounties', 'circles', 'leaderboards', 'tools', 'mod'].includes(initial)) openTab(initial);
  try {
    await Promise.all([loadPosts(), loadIdeas(), loadBounties(), loadCircles(), loadLeaderboards(), loadModQueue()]);
    $('#communityDot').className = 'dot ok'; setText('#communityStatus', 'API online');
    if (circleMatch) openCircleDetail(decodeURIComponent(circleMatch[1]));
  } catch { $('#communityDot').className = 'dot err'; setText('#communityStatus', 'API unavailable'); }
}
$$('.community-tabs button').forEach(btn => btn.addEventListener('click', () => openTab(btn.dataset.tab)));
$$('[data-open-tab]').forEach(a => a.addEventListener('click', (ev) => { ev.preventDefault(); openTab(a.dataset.openTab); }));
$$('[data-sort]').forEach(btn => btn.addEventListener('click', () => {
  activePostSort = btn.dataset.sort || 'hot';
  $$('[data-sort]').forEach(b => b.classList.toggle('active', b === btn));
  loadPosts();
}));
wireImagePicker('post', '#postImage', '#postImageBtn', '#postImagePreview', '#postImagePreviewImg', '#postImageClear', '#postResult');
wireImagePicker('comment', '#commentImage', '#commentImageBtn', '#commentImagePreview', '#commentImagePreviewImg', '#commentImageClear', '#commentResult');
wireImagePicker('circlePost', '#circlePostImage', '#circlePostImageBtn', '#circlePostImagePreview', '#circlePostImagePreviewImg', '#circlePostImageClear', '#circlePostResult');
$('#postMessageBtn')?.addEventListener('click', async () => {
  try {
    const d = await post('/community/posts', { name: $('#postName').value, category: $('#postCategory').value, message: $('#postMessage').value, image: takeImage('post') });
    setToast('#postResult', 'Posted ' + (d.post_id || ''), 'ok'); $('#postMessage').value = ''; resetImagePreview('#postImagePreview', '#postImagePreviewImg'); await loadPosts();
  } catch (e) { setToast('#postResult', e.message, 'err'); }
});
let replyingToCommentId = '';
$('#submitComment')?.addEventListener('click', async () => {
  try {
    const id = $('#commentPostId').value || activeCommentPost;
    const d = await post('/community/posts/' + encodeURIComponent(id) + '/comments', { name: $('#commentName').value, message: $('#commentMessage').value, parent_comment_id: replyingToCommentId, image: takeImage('comment') });
    setToast('#commentResult', replyingToCommentId ? 'Replied ' + (d.comment_id || '') : 'Commented ' + (d.comment_id || ''), 'ok');
    $('#commentMessage').value = '';
    resetImagePreview('#commentImagePreview', '#commentImagePreviewImg');
    replyingToCommentId = '';
    $('#submitComment').textContent = 'Comment';
    await loadComments(id); await loadPosts();
  } catch (e) { setToast('#commentResult', e.message, 'err'); }
});
$('#submitIdea')?.addEventListener('click', async () => {
  try {
    const d = await post('/community/improvements', { title: $('#ideaTitle').value, details: $('#ideaDetails').value, category: $('#ideaCategory').value, author: $('#ideaAuthor').value });
    setToast('#ideaResult', 'Submitted ' + (d.idea_id || ''), 'ok'); $('#ideaTitle').value = ''; $('#ideaDetails').value = ''; await loadIdeas();
  } catch (e) { setToast('#ideaResult', e.message, 'err'); }
});
$('#submitReport')?.addEventListener('click', async () => {
  try {
    const d = await post('/community/reports', { post_id: $('#reportPostId').value, reason: $('#reportReason').value });
    setToast('#reportResult', 'Report sent ' + (d.report_id || ''), 'ok'); $('#reportPostId').value = ''; $('#reportReason').value = ''; await loadModQueue();
  } catch (e) { setToast('#reportResult', e.message, 'err'); }
});
$('#refreshPosts')?.addEventListener('click', loadPosts);
$('#refreshComments')?.addEventListener('click', () => loadComments());
$('#commentLookupBtn')?.addEventListener('click', () => loadComments($('#commentPostId')?.value || ''));
$('#refreshIdeas')?.addEventListener('click', loadIdeas);
$('#refreshBounties')?.addEventListener('click', loadBounties);
$('#refreshLeaderboards')?.addEventListener('click', loadLeaderboards);
$('#refreshMod')?.addEventListener('click', loadModQueue);
$('#refreshCircles')?.addEventListener('click', loadCircles);
$('#circleSearch')?.addEventListener('input', renderCircleFeed);
$('#btnBackToCircles')?.addEventListener('click', backToCircles);
$('#circlePostBtn')?.addEventListener('click', async () => {
  if (!activeCircleId) return;
  try {
    const d = await post('/community/posts', { name: $('#circlePostName').value, category: 'general', message: $('#circlePostMessage').value, circle_id: activeCircleId, image: takeImage('circlePost') });
    setToast('#circlePostResult', 'Posted ' + (d.post_id || ''), 'ok'); $('#circlePostMessage').value = ''; resetImagePreview('#circlePostImagePreview', '#circlePostImagePreviewImg'); await loadCirclePosts(activeCircleId);
  } catch (e) { setToast('#circlePostResult', e.message, 'err'); }
});
$$('[data-leader-tab]').forEach(btn => btn.addEventListener('click', () => {
  activeLeaderTab = btn.dataset.leaderTab || 'top_miners';
  $$('[data-leader-tab]').forEach(b => b.classList.toggle('active', b === btn));
  renderLeaderboardTab();
}));
$('#submitCircle')?.addEventListener('click', async () => {
  try {
    const d = await post('/community/circles', { name: $('#circleName').value, description: $('#circleDescription').value, rules: $('#circleRules').value, creator: $('#circleCreator').value });
    setToast('#circleResult', 'Proposed ' + (d.circle_id || ''), 'ok'); $('#circleName').value = ''; $('#circleDescription').value = ''; $('#circleRules').value = ''; await loadCircles();
  } catch (e) { setToast('#circleResult', e.message, 'err'); }
});
document.addEventListener('click', async (ev) => {
  const report = ev.target.closest('[data-report-post]');
  if (report) { openTab('tools'); $('#reportPostId').value = report.dataset.reportPost || ''; $('#reportReason').focus(); return; }
  const comments = ev.target.closest('[data-open-comments]');
  if (comments) { openTab('comments'); await loadComments(comments.dataset.openComments || ''); return; }
  const replyTo = ev.target.closest('[data-reply-to]');
  if (replyTo) {
    replyingToCommentId = replyTo.dataset.replyTo || '';
    $('#submitComment').textContent = replyingToCommentId ? 'Post reply' : 'Comment';
    $('#commentMessage').focus();
    return;
  }
  const pinPost = ev.target.closest('[data-pin-post]');
  if (pinPost) {
    const circleId = pinPost.dataset.circleId;
    const wasPinned = pinPost.textContent === 'Unpin';
    try {
      await post('/community/circles/' + encodeURIComponent(circleId) + '/pin', {
        creator: ($('#circleCreator')?.value || '').trim(),
        post_id: wasPinned ? '' : pinPost.dataset.pinPost,
      });
      await loadCircles();
      await loadCirclePosts(circleId);
    } catch (e) { alert('Could not pin: ' + e.message); }
    return;
  }
  const votePost = ev.target.closest('[data-vote-post]');
  if (votePost && votePost.dataset.votePost) {
    try { await post('/community/posts/' + encodeURIComponent(votePost.dataset.votePost) + '/vote', { direction: votePost.dataset.direction || 'up', voter: localStorage.getItem('nc.apiKey.v1') || 'browser' }); await loadPosts(); }
    catch (e) { setToast('#postResult', e.message, 'err'); }
    return;
  }
  const vote = ev.target.closest('[data-vote-idea]');
  if (vote && vote.dataset.voteIdea) {
    try { await post('/community/improvements/' + encodeURIComponent(vote.dataset.voteIdea) + '/vote', {}); await loadIdeas(); }
    catch (e) { setToast('#ideaResult', e.message, 'err'); }
    return;
  }
  const openCircle = ev.target.closest('[data-open-circle]');
  if (openCircle && openCircle.dataset.openCircle) { openCircleDetail(openCircle.dataset.openCircle); return; }
  const join = ev.target.closest('[data-join-circle]');
  if (join && join.dataset.joinCircle) {
    try {
      const member = $('#circleCreator').value || localStorage.getItem('nc.apiKey.v1') || prompt('Your name to join this circle:') || '';
      if (!member) return;
      await post('/community/circles/' + encodeURIComponent(join.dataset.joinCircle) + '/join', { member });
      await loadCircles();
      if (activeCircleId) openCircleDetail(activeCircleId);
    } catch (e) { $('#circleFeed').insertAdjacentHTML('afterbegin', `<div class="empty-state">${esc(e.message)}</div>`); }
    return;
  }
  const mod = ev.target.closest('[data-mod-target]');
  if (mod) {
    try { await post('/community/moderation', { target: mod.dataset.modTarget, action: mod.dataset.modAction }); await loadModQueue(); await loadPosts(); }
    catch (e) { $('#modQueue').insertAdjacentHTML('afterbegin', `<div class="empty-state">${esc(e.message)}</div>`); }
  }
});
boot();
