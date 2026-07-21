'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const words = value => String(value || 'unknown').replace(/_/g, ' ');
const amount = sats => new Intl.NumberFormat().format(Number(sats || 0)) + ' sats';

function fields(record) {
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(record, null, 2);
  return pre.outerHTML;
}

function proposalCard(proposal) {
  const title = proposal.title || proposal.memo || proposal.proposal_id || 'Treasury proposal';
  return `<article class="card"><div class="section-head"><h3>${esc(title)}</h3><span class="pill">${esc(words(proposal.status))}</span></div><p><strong>${esc(amount(proposal.amount_sats))}</strong></p><p class="muted">Recipient: <span class="mono">${esc(proposal.to_address || 'Not set')}</span></p>${fields(proposal)}</article>`;
}

async function loadTreasury() {
  $('#treasuryStatus').textContent = 'Refreshing treasury records...';
  try {
    const response = await fetch('/api/treasury/governance');
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
    $('#proposalCount').textContent = Number(data.proposal_count || 0).toLocaleString();
    $('#pendingCount').textContent = Number(data.pending || 0).toLocaleString();
    $('#readyCount').textContent = Number(data.ready_for_signing || 0).toLocaleString();
    $('#treasuryAddresses').innerHTML = fields(data.treasury_addresses || []);
    $('#treasuryPolicy').innerHTML = fields(data.policy || {});
    $('#treasuryProposals').innerHTML = (data.proposals || []).length ? data.proposals.map(proposalCard).join('') : '<article class="card"><h3>No proposals yet</h3><p class="muted">New treasury proposals will appear here when they are submitted.</p></article>';
    $('#treasuryStatus').textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    $('#treasuryStatus').textContent = `Treasury unavailable: ${error.message}`;
    $('#treasuryProposals').innerHTML = '<article class="card"><h3>Could not load treasury data</h3><p class="muted">Check node availability, then refresh.</p></article>';
  }
}

$('#refreshTreasury').addEventListener('click', loadTreasury);
loadTreasury();
