'use strict';
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let catalog = null;
function ratingClass(r){ return Number(r) >= 7 ? 'strong' : (Number(r) < 6 ? 'weak' : ''); }
function featureCard(f){ return `<article class="feature-card"><header><h3>${esc(f.name)}</h3><span class="rating-pill ${ratingClass(f.rating)}">${esc(f.rating)}/10</span></header><p>${esc(f.summary)}</p><small><b>${esc(f.status)}</b>${f.next_fix ? ' · Next: ' + esc(f.next_fix) : ''}</small></article>`; }
function liveBadge(status){ return `<span class="rating-pill ${status==='working'?'strong':status==='missing'?'weak':''}">${esc(status)}</span>`; }
function render(){
  if(!catalog) return;
  const q = ($('#featureSearch').value || '').toLowerCase();
  const cat = $('#featureCategory').value || '';
  const min = Number($('#featureMinimum').value || 0);
  const out = $('#featureCatalog');
  const groups = catalog.groups || {};
  out.innerHTML = Object.keys(groups).filter(name => !cat || name === cat).map(name => {
    const items = (groups[name] || []).filter(f => Number(f.rating) >= min && (!q || (f.name + ' ' + f.summary + ' ' + f.next_fix + ' ' + f.category).toLowerCase().includes(q)));
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
    $('#impactFixes').innerHTML = (catalog.top_impact_fixes || []).map(f => `<div class="impact-item"><b>#${esc(f.rank)}</b><span><strong>${esc(f.area)}</strong> — ${esc(f.fix)}</span><small>${esc(f.impact)}</small></div>`).join('');
    if(liveRes.status === 'fulfilled'){
      const live = await liveRes.value.json();
      $('#liveFeatureStatus').innerHTML = (live.probes || []).map(p => `<div class="impact-item"><b>${liveBadge(p.status)}</b><span><strong>${esc(p.label)}</strong> — ${esc(p.present)}/${esc(p.expected)} files wired</span><small>${esc(p.route)}</small></div>`).join('') || 'No live probes.';
    } else $('#liveFeatureStatus').textContent = 'Live feature probes unavailable.';
    render();
  }catch(e){ $('#featureDot').className='dot err'; $('#featureStatus').textContent='Catalog unavailable'; $('#featureCatalog').innerHTML='<div class="card">'+esc(e.message)+'</div>'; }
}
['featureSearch','featureCategory','featureMinimum'].forEach(id => $('#'+id)?.addEventListener('input', render));
boot();
