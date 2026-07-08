'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let activePostSort = 'hot';
let activeCommentPost = '';

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
function redditCard({ postId = '', score = 0, title = '', body = '', meta = [], tag = '', commentCount = 0, actions = [] }) {
  const metaHtml = [tag ? `<span class="tag">${esc(tag)}</span>` : '', ...meta.map(esc)].filter(Boolean).map(x => x.startsWith('<') ? x : `<span>${x}</span>`).join('');
  const actionHtml = actions.map(a => a.html || `<button type="button" ${a.attr || ''}>${esc(a.label)}</button>`).join('');
  return `<article class="reddit-card" data-post-id="${esc(postId)}"><div class="vote-rail"><button type="button" data-vote-post="${esc(postId)}" data-direction="up" aria-label="upvote">▲</button><strong>${esc(score)}</strong><button type="button" data-vote-post="${esc(postId)}" data-direction="down" aria-label="downvote">▼</button></div><div class="post-body"><div class="post-meta">${metaHtml}</div><h3>${esc(title)}</h3><p>${esc(body)}</p><div class="post-stats"><button type="button" data-open-comments="${esc(postId)}">${Number(commentCount || 0)} comments</button><span>${esc(postId)}</span></div>${actionHtml ? `<div class="post-actions">${actionHtml}</div>` : ''}</div></article>`;
}
function cardPost(p) {
  return redditCard({
    postId: p.post_id || '',
    score: Number(p.score || p.votes || 0),
    title: p.title || (p.category === 'help' ? 'Help request' : 'Community post'),
    body: p.message || '',
    tag: p.category || 'general',
    commentCount: p.comment_count || 0,
    meta: ['u/' + (p.name || p.author || 'Anonymous'), timeLabel(p.created_at), (p.sort ? 'sort:' + p.sort : '')].filter(Boolean),
    actions: [{ html: `<button type="button" data-report-post="${esc(p.post_id || '')}">Report</button>` }]
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
function commentCard(c) {
  return `<article class="comment-card"><div><b>u/${esc(c.name || 'Anonymous')}</b><span>${esc(timeLabel(c.created_at))}</span></div><p>${esc(c.message || '')}</p></article>`;
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
  if (!id) { out.innerHTML = '<p class="muted">Pick a post to view comments.</p>'; return; }
  activeCommentPost = id;
  $('#commentPostId').value = id;
  try {
    const d = await api('/community/posts/' + encodeURIComponent(id) + '/comments');
    out.innerHTML = (d.comments || []).length ? d.comments.map(commentCard).join('') : '<p class="muted">No comments yet.</p>';
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
async function loadLeaderboards() {
  const out = $('#leaderboardsOut');
  try {
    const d = await api('/community/leaderboards');
    const summary = d.summary ? `<div class="leader-summary"><span>${esc(d.summary.miner_count || 0)} miners</span><span>${esc(d.summary.earner_count || 0)} earners</span><span>${esc(d.summary.donor_count || 0)} donors</span></div>` : '';
    out.innerHTML = summary + [leaderboardTable('Top miners', d.top_miners), leaderboardTable('Top earners', d.top_earners), leaderboardTable('Top donors', d.top_donors)].join('');
    const side = $('#sidebarLeaders');
    if (side) side.innerHTML = (d.top_miners || []).slice(0, 5).map((r, i) => `<div class="mini-leader"><span>#${i + 1} ${esc(r.short_id || shortId(r.id || 'unknown'))}</span><b>${amount(r.amount)} NET</b></div>`).join('') || '<p class="muted">No miners yet.</p>';
  } catch (e) { out.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
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
  if (['posts', 'comments', 'ideas', 'bounties', 'leaderboards', 'tools', 'mod'].includes(initial)) openTab(initial);
  try {
    await Promise.all([loadPosts(), loadIdeas(), loadBounties(), loadLeaderboards(), loadModQueue()]);
    $('#communityDot').className = 'dot ok'; setText('#communityStatus', 'API online');
  } catch { $('#communityDot').className = 'dot err'; setText('#communityStatus', 'API unavailable'); }
}
$$('.community-tabs button').forEach(btn => btn.addEventListener('click', () => openTab(btn.dataset.tab)));
$$('[data-open-tab]').forEach(a => a.addEventListener('click', (ev) => { ev.preventDefault(); openTab(a.dataset.openTab); }));
$$('[data-sort]').forEach(btn => btn.addEventListener('click', () => {
  activePostSort = btn.dataset.sort || 'hot';
  $$('[data-sort]').forEach(b => b.classList.toggle('active', b === btn));
  loadPosts();
}));
$('#postMessageBtn')?.addEventListener('click', async () => {
  try {
    const d = await post('/community/posts', { name: $('#postName').value, category: $('#postCategory').value, message: $('#postMessage').value });
    setToast('#postResult', 'Posted ' + (d.post_id || ''), 'ok'); $('#postMessage').value = ''; await loadPosts();
  } catch (e) { setToast('#postResult', e.message, 'err'); }
});
$('#submitComment')?.addEventListener('click', async () => {
  try {
    const id = $('#commentPostId').value || activeCommentPost;
    const d = await post('/community/posts/' + encodeURIComponent(id) + '/comments', { name: $('#commentName').value, message: $('#commentMessage').value });
    setToast('#commentResult', 'Commented ' + (d.comment_id || ''), 'ok'); $('#commentMessage').value = ''; await loadComments(id); await loadPosts();
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
$('#refreshIdeas')?.addEventListener('click', loadIdeas);
$('#refreshBounties')?.addEventListener('click', loadBounties);
$('#refreshLeaderboards')?.addEventListener('click', loadLeaderboards);
$('#refreshMod')?.addEventListener('click', loadModQueue);
document.addEventListener('click', async (ev) => {
  const report = ev.target.closest('[data-report-post]');
  if (report) { openTab('tools'); $('#reportPostId').value = report.dataset.reportPost || ''; $('#reportReason').focus(); return; }
  const comments = ev.target.closest('[data-open-comments]');
  if (comments) { openTab('comments'); await loadComments(comments.dataset.openComments || ''); return; }
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
  const mod = ev.target.closest('[data-mod-target]');
  if (mod) {
    try { await post('/community/moderation', { target: mod.dataset.modTarget, action: mod.dataset.modAction }); await loadModQueue(); await loadPosts(); }
    catch (e) { $('#modQueue').insertAdjacentHTML('afterbegin', `<div class="empty-state">${esc(e.message)}</div>`); }
  }
});
boot();
