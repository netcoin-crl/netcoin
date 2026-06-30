'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, options = {}) {
  const res = await fetch('/api' + path, options);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok || data.error) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}
function post(path, body) { return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
function setText(id, value) { const el = $(id); if (el) el.textContent = value; }
function timeLabel(t) { if (!t) return 'now'; try { return new Date(Number(t) * 1000).toLocaleString(); } catch { return String(t); } }
function cardPost(p) {
  const title = p.title ? `<h3>${esc(p.title)}</h3>` : '';
  const name = p.name || p.author || 'Anonymous';
  return `<article class="post">${title}<div class="meta"><span>${esc(p.category || 'general')}</span><span>by ${esc(name)}</span><span>${esc(timeLabel(p.created_at))}</span></div><p>${esc(p.message)}</p></article>`;
}
function cardIdea(i) {
  return `<article class="idea"><h3>${esc(i.title || 'Untitled idea')}</h3><div class="meta"><span>${esc(i.category || 'general')}</span><span>${Number(i.votes || 0)} votes</span><span>${esc(timeLabel(i.created_at))}</span></div><p>${esc(i.details || i.description || '')}</p></article>`;
}
function cardBounty(b) {
  return `<article class="bounty"><h3>${esc(b.title || b.bounty_id)}</h3><div class="meta"><span>${esc(b.status || 'open')}</span><span>${esc(b.reward || '0')} NET</span></div><p>${esc(b.description || 'No description yet.')}</p></article>`;
}
async function loadPosts() {
  try {
    const d = await api('/community/posts?limit=80');
    setText('#postCount', d.count ?? (d.posts || []).length);
    $('#postFeed').innerHTML = (d.posts || []).length ? (d.posts || []).map(cardPost).join('') : '<p class="muted">No messages yet. Be the first to post.</p>';
  } catch (e) { $('#postFeed').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
async function loadIdeas() {
  try {
    const d = await api('/community/improvements');
    setText('#ideaCount', d.count ?? (d.improvements || []).length);
    $('#ideaFeed').innerHTML = (d.improvements || []).length ? (d.improvements || []).map(cardIdea).join('') : '<p class="muted">No improvement ideas yet.</p>';
  } catch (e) { $('#ideaFeed').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
async function loadBounties() {
  try {
    const d = await api('/community/bounties');
    const open = (d.bounties || []).filter(b => (b.status || 'open') === 'open');
    setText('#bountyCount', open.length || (d.bounties || []).length);
    $('#bountyFeed').innerHTML = (d.bounties || []).length ? (d.bounties || []).map(cardBounty).join('') : '<p class="muted">No bounties are open yet.</p>';
  } catch (e) { $('#bountyFeed').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
async function loadLeaderboards() {
  try { $('#leaderboardsOut').textContent = JSON.stringify(await api('/community/leaderboards'), null, 2); }
  catch (e) { $('#leaderboardsOut').textContent = JSON.stringify({ ok:false, error:e.message }, null, 2); }
}
async function boot() {
  try {
    await Promise.all([loadPosts(), loadIdeas(), loadBounties(), loadLeaderboards()]);
    $('#communityDot').className = 'dot ok';
    setText('#communityStatus', 'Community API online');
  } catch {
    $('#communityDot').className = 'dot err';
    setText('#communityStatus', 'Community API unavailable');
  }
}
$('#postMessageBtn').onclick = async () => {
  try {
    const payload = { name: $('#postName').value, category: $('#postCategory').value, message: $('#postMessage').value };
    const d = await post('/community/posts', payload);
    $('#postResult').textContent = 'Posted: ' + (d.post_id || 'ok');
    $('#postMessage').value = '';
    await loadPosts();
  } catch (e) { $('#postResult').textContent = 'Post failed: ' + e.message; }
};
$('#submitIdea').onclick = async () => {
  try {
    const payload = { title: $('#ideaTitle').value, details: $('#ideaDetails').value, category: $('#ideaCategory').value, author: $('#ideaAuthor').value };
    const d = await post('/community/improvements', payload);
    $('#ideaResult').textContent = 'Submitted: ' + (d.idea_id || 'ok');
    $('#ideaTitle').value = ''; $('#ideaDetails').value = '';
    await loadIdeas();
  } catch (e) { $('#ideaResult').textContent = 'Idea failed: ' + e.message; }
};
$('#refreshPosts').onclick = loadPosts;
$('#refreshIdeas').onclick = loadIdeas;
boot();
