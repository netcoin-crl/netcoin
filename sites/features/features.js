'use strict';
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Shown once as the page-level disclaimer banner; repeating it on every card is noise.
const GENERIC_AVAILABILITY_NOTE = 'Internal readiness rating only; not externally audited, mainnet-ready, or real-money production software.';
let catalog = null;
function ratingClass(r){ return Number(r) >= 7 ? 'strong' : (Number(r) < 6 ? 'weak' : ''); }
function statusClass(value){
  const text = String(value || '').toLowerCase();
  if(text.includes('available')) return 'available';
  if(text.includes('partial') || text.includes('status') || text.includes('guide')) return 'partial';
  if(text.includes('experimental') || text.includes('internal') || text.includes('not exposed')) return 'limited';
  return '';
}
function surfaceBadge(label, value){ return `<span class="surface-badge ${statusClass(value)}"><b>${esc(label)}</b>${esc(value || 'Not exposed')}</span>`; }
function featureCard(f){
  const workflow = f.ui_entrypoint ? `<a class="feature-workflow" href="${esc(f.ui_entrypoint)}">Open workflow</a>` : `<span class="feature-workflow unavailable">No browser workflow</span>`;
  return `<article class="feature-card" data-badge="${esc(f.badge)}"><header><h3>${esc(f.name)}</h3><span class="rating-pill ${ratingClass(f.rating)}">${esc(f.rating)}/10</span></header>` +
    `<div class="availability-row"><span class="availability-chip ${statusClass(f.availability)}">${esc(f.badge || f.availability || 'Testnet only')}</span><span class="prod-chip">Production-ready: ${f.production_ready ? 'yes' : 'no'}</span></div>` +
    `<p>${esc(f.summary)}</p>` +
    `<div class="surface-grid">${surfaceBadge('UI', f.ui)}${surfaceBadge('API', f.api)}${surfaceBadge('CLI', f.cli)}${surfaceBadge('Tests', f.test_coverage)}</div>` +
    `<div class="feature-exposure"><b>${esc(f.audience || 'Unspecified audience')}</b><span>${esc(f.access_mode || 'Unspecified access')}</span><p>${esc(f.workflow || 'No workflow recorded.')}</p>${workflow}</div>` +
    `<small><b>${esc(f.status)}</b>${f.next_fix ? ' · Next: ' + esc(f.next_fix) : ''}</small>` +
    (f.availability_notes && f.availability_notes !== GENERIC_AVAILABILITY_NOTE ? `<small class="availability-note">${esc(f.availability_notes)}</small>` : '') +
    `</article>`;
}
function liveBadge(status){ return `<span class="rating-pill ${status==='working'?'strong':status==='missing'?'weak':''}">${esc(status)}</span>`; }
function render(){
  if(!catalog) return;
  const q = ($('#featureSearch').value || '').toLowerCase();
  const cat = $('#featureCategory').value || '';
  const min = Number($('#featureMinimum').value || 0);
  const surface = $('#featureSurface').value || '';
  const out = $('#featureCatalog');
  const groups = catalog.groups || {};
  function matchesSurface(f){
    if(!surface) return true;
    const value = String(f[surface] || '').toLowerCase();
    return value.includes('available') || value.includes('guide/status') || value.includes('simulation available');
  }
  out.innerHTML = Object.keys(groups).filter(name => !cat || name === cat).map(name => {
    const items = (groups[name] || []).filter(f => Number(f.rating) >= min && matchesSurface(f) && (!q || (f.name + ' ' + f.summary + ' ' + f.next_fix + ' ' + f.category + ' ' + f.badge + ' ' + f.ui + ' ' + f.api + ' ' + f.cli + ' ' + f.test_coverage + ' ' + f.audience + ' ' + f.access_mode + ' ' + f.workflow).toLowerCase().includes(q)));
    if(!items.length) return '';
    return `<section class="feature-section"><h2>${esc(name)}</h2><div class="feature-grid">${items.map(featureCard).join('')}</div></section>`;
  }).join('') || '<div class="card">No matching features.</div>';
}
async function boot(){
  try{
    const [catalogRes, liveRes] = await Promise.allSettled([fetch('/api/features'), fetch('/api/feature-status')]);
    if(catalogRes.status !== 'fulfilled') throw new Error('Catalog fetch failed');
    catalog = await catalogRes.value.json();
    const s = catalog.summary || {};
    $('#featureDot').className='dot ok'; $('#featureStatus').textContent='Catalog online';
    $('#featureStats').innerHTML = `<div><b>${esc(s.feature_count || 0)}</b><span>features</span></div><div><b>${esc(s.average_rating || '—')}</b><span>avg rating</span></div><div><b>${esc(s.strong_count || 0)}</b><span>7+ strong</span></div><div><b>${esc(s.weak_count || 0)}</b><span>below 6</span></div>`;
    $('#featureCategory').innerHTML += Object.keys(catalog.groups || {}).map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
    $('#catalogDisclaimer').textContent = catalog.disclaimer || 'Public-testnet ratings only. Not a production readiness claim.';
    $('#availabilityScale').innerHTML = Object.entries(catalog.availability_scale || {}).map(([k,v]) => `<div><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join('');
    $('#impactFixes').innerHTML = (catalog.top_impact_fixes || []).map(f => `<div class="impact-item"><b>#${esc(f.rank)}</b><span><strong>${esc(f.area)}</strong> — ${esc(f.fix)}</span><small>${esc(f.impact)}</small></div>`).join('');
    if(liveRes.status === 'fulfilled'){
      const live = await liveRes.value.json();
      $('#liveFeatureStatus').innerHTML = (live.probes || []).map(p => `<div class="impact-item"><b>${liveBadge(p.status)}</b><span><strong>${esc(p.label)}</strong> — ${esc(p.present)}/${esc(p.expected)} files wired</span><small>${esc(p.route)}</small></div>`).join('') || 'No live probes.';
    } else $('#liveFeatureStatus').textContent = 'Live feature probes unavailable.';
    render();
  }catch(e){ $('#featureDot').className='dot err'; $('#featureStatus').textContent='Catalog unavailable'; $('#featureCatalog').innerHTML='<div class="card">'+esc(e.message)+'</div>'; }
}
['featureSearch','featureCategory','featureMinimum','featureSurface'].forEach(id => $('#'+id)?.addEventListener('input', render));
boot();
