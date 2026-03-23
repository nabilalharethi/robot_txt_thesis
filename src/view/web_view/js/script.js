const API='';
let _allResults=[];
let _charts={};

function showPage(name,btn){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if(btn)btn.classList.add('active');
}

async function runSingleAnalysis(){
  let url=document.getElementById('input-url').value.trim();
  const name=document.getElementById('input-name').value.trim();
  const group=document.getElementById('input-group').value.trim();
  const btn=document.getElementById('btn-analyze');
  const spin=document.getElementById('analyze-spinner');
  const out=document.getElementById('single-result');
  if(!url){out.innerHTML='<div class="error-msg">Please enter a URL.</div>';return;}
  if(!url.startsWith('http'))url='https://'+url;
  try{const u=new URL(url);url=u.origin;}catch(e){}
  btn.disabled=true;spin.style.display='inline-block';
  out.innerHTML='<div class="info-msg">Fetching robots.txt from '+url+' ...</div>';
  try{
    const resp=await fetch(API+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,name,group})});
    if(!resp.ok){const e=await resp.json().catch(()=>({error:'Server error '+resp.status}));throw new Error(e.error||'Server error '+resp.status);}
    const data=await resp.json();
    if(data.error)throw new Error(data.error);
    out.innerHTML=renderResultCard(data);
  }catch(e){
    out.innerHTML=`<div class="error-msg"><strong>Could not fetch robots.txt.</strong><br><br>${e.message}<br><br><span style="font-size:11px">Common causes: the site blocks automated requests, has no robots.txt, or the server timed out. Try just the homepage domain, e.g. <code>https://www.bbc.co.uk</code> -- do not include paths like /news.</span></div>`;
  }finally{btn.disabled=false;spin.style.display='none';}
}
document.getElementById('input-url').addEventListener('keydown',e=>{if(e.key==='Enter')runSingleAnalysis();});

function renderResultCard(r){
  if(r.strategy==='ERROR'){
    const reason=r.error_type||'unknown';
    const hints={'404':'The site has no robots.txt file at /robots.txt.','timeout':'The server did not respond in time.','SSL':'SSL/TLS certificate issue on the remote server.'};
    const hint=Object.entries(hints).find(([k])=>reason.includes(k))?.[1]||'The server may be blocking automated requests or the domain is unreachable.';
    return`<div class="result-card"><div class="result-header"><div><div class="result-site-name">${r.name||r.url}</div><div class="result-url">${r.url}</div></div><span class="badge badge-error">ERROR</span></div><p style="color:var(--danger);font-size:13px;margin-bottom:8px">Failed: ${reason}</p><p style="color:var(--muted);font-size:12px">${hint}</p></div>`;
  }
  const cs=(r.compliance_status||'').toLowerCase();
  const score=r.compliance_score||0;
  const pct=Math.round(score*100);
  const sc=pct>=80?'var(--accent)':pct>=40?'var(--warn)':'var(--danger)';
  const tc={'Tier 5':'#ff5c5c','Tier 4b':'#4da6ff','Tier 4a':'#8338ec','Tier 3':'#00e5a0','Tier 2':'#fb8500','Tier 1':'#6b7570'}[r.strategy_tier]||'#6b7570';
  const la=r.layer_analysis||r.compliance?.layer_analysis||{};
  const layers=['app_layer','infra_layer','google_ai'].map(k=>{
    const l=la[k]||{};
    const lbl={app_layer:'APP LAYER &middot; 35%',infra_layer:'INFRA LAYER &middot; 45%',google_ai:'GOOGLE AI &middot; 20%'}[k];
    return`<div class="layer-cell"><div class="layer-name">${lbl}</div><div class="layer-status ${l.effective?'layer-effective':'layer-ineffective'}">${l.effective?'&#10003; Blocked':'&#10007; Exposed'}</div>${l.conflict_undermined?'<div style="font-size:10px;color:var(--danger);margin-top:2px">&#8593; Conflict undermines</div>':''}</div>`;
  }).join('');

  const meanings={
    COMPLIANT:{cls:'',txt:'This site has a valid, effective machine-readable opt-out under EU AI Act Recital 105 / Article 53(1)(c). All three bot layers are blocked with no internal contradictions. AI training data providers are legally obliged to respect this configuration.'},
    NOMINAL:{cls:'warn',txt:'<strong>Enumeration Fallacy detected.</strong> This site names AI bots (showing intent to block) but HIGH severity directive conflicts -- a wildcard <code>Allow: /</code> overriding per-bot <code>Disallow: /</code> entries -- make the blocking semantically ineffective. Binary parsers would count this site as protected. The SCA shows it is not.'},
    PARTIAL:{cls:'warn',txt:'This site blocks some but not all bot layers. A partial opt-out exists but the missing layers are a compliance gap under EU AI Act Article 53(1)(c). The score reflects exactly which layers are covered.'},
    NON_COMPLIANT:{cls:'danger',txt:'No effective AI opt-out. All AI training data collectors have full access. No reservation of rights exists under EU AI Act Recital 105. The site has either no AI entries in robots.txt or the file is open by default.'},
  };
  const m=meanings[r.compliance_status]||{cls:'',txt:''};
  const conflicts=(r.conflicts||[]).slice(0,8).map(c=>`<div class="conflict-item ${c.severity==='HIGH'?'high':''}"><div class="conflict-type">${c.severity} &middot; ${c.type}</div><div class="conflict-agent">${c.affected_agent}</div><div class="conflict-detail">${c.detail||''}</div></div>`).join('');

  return`<div class="result-card">
    <div class="result-header">
      <div>
        <div class="result-site-name">${r.name||r.url}</div>
        <div class="result-url">${r.url}</div>
        ${r.redirected?`<div style="font-size:10px;color:var(--warn);margin-top:3px;font-family:var(--mono)">&#8611; redirected to ${r.redirect_target}</div>`:''}
      </div>
      <span class="badge badge-${cs}">${r.compliance_status||'--'}</span>
    </div>
    <div class="tier-bar">
      <span class="tier-pip" style="background:${tc}"></span>
      <div><div class="tier-text">${r.strategy||r.strategy_tier}</div><div class="tier-desc">${r.tier_description||r.tier_label||''}</div></div>
    </div>
    <div class="score-bar-wrap">
      <div class="score-label"><span>Compliance score</span><span style="color:${sc}">${pct}%</span></div>
      <div class="score-track"><div class="score-fill" style="width:${pct}%;background:${sc}"></div></div>
    </div>
    <div class="layers-grid">${layers}</div>
    ${m.txt?`<div class="meaning-box ${m.cls}"><h4>What this means</h4><p>${m.txt}</p></div>`:''}
    ${(r.conflict_count||0)>0?`<div class="conflicts-list"><div style="font-size:11px;font-family:var(--mono);color:var(--muted);margin:16px 0 8px;letter-spacing:.06em">CONFLICTS (${r.conflict_count})</div>${conflicts}${(r.conflicts||[]).length>8?`<div style="font-size:11px;color:var(--muted);text-align:center;padding:8px">... and ${r.conflicts.length-8} more</div>`:''}</div>`:'<div style="margin-top:14px;font-size:12px;color:var(--accent);font-family:var(--mono)">&#10003; No directive conflicts detected</div>'}
    <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border);font-size:11px;color:var(--muted);font-family:var(--mono)">${r.eu_ai_act_ref||r.compliance?.eu_ai_act_ref||'EU AI Act Recital 105 / Article 53(1)(c)'}</div>
${r.raw_content ? `
    <div style="margin-top:16px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <div style="font-size:10px;font-family:var(--mono);color:var(--muted);letter-spacing:.08em;text-transform:uppercase">robots.txt — raw content</div>
        <button onclick="var b=document.getElementById('raw-body');var expanded=b.style.display==='block';b.style.display=expanded?'none':'block';this.textContent=expanded?'▼ expand':'▲ collapse';" style="font-size:10px;font-family:var(--mono);color:var(--muted);background:none;border:none;cursor:pointer;padding:0">▼ expand</button>
      </div>
      <div id="raw-body" style="display:none;background:#FEFEFE;border:1px solid var(--border);border-radius:6px;overflow:auto;max-height:380px">
        <pre style="margin:0;padding:0;font-family:var(--mono);font-size:11px;line-height:1.8">${highlightRobotsLine(r.raw_content, r.conflicts||[], r.line_map||{})}</pre>
      </div>
    </div>` : ''}
  </div>`;
}

async function runBatchAnalysis(){
  const btn=document.getElementById('btn-batch');
  const spin=document.getElementById('batch-spinner');
  btn.disabled=true;spin.style.display='inline-block';
  try{
    const resp=await fetch(API+'/analyze-batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({targets_file:'targets.json'})});
    const data=await resp.json();
    if(data.error)throw new Error(data.error);
    _allResults=data.results||[];
    renderTable(_allResults);
    renderThesisCharts(_allResults);
  }catch(e){alert('Batch error: '+e.message);}
  finally{btn.disabled=false;spin.style.display='none';}
}



function renderTable(results){
  document.getElementById('table-count').textContent=results.filter(r=>r.strategy!=='ERROR').length;
  fillTable(results);
}
function fillTable(results){
  const tbody=document.getElementById('results-tbody');
  tbody.innerHTML='';
  results.forEach(r=>{
    if(r.strategy==='ERROR')return;
    const tr=document.createElement('tr');
    tr.onclick=()=>openDetail(r);
    const tier=r.strategy_tier||'';
    const tc=tier==='Tier 5'?'tp5':tier==='Tier 4b'?'tp4b':tier==='Tier 4a'?'tp4a':tier==='Tier 3'?'tp3':tier==='Tier 2'?'tp2':'tp1';
    const cs=(r.compliance_status||'').toLowerCase();
    const score=Math.round((r.compliance_score||0)*100);
    tr.innerHTML=`<td class="name-col">${r.name||r.url}</td><td>${r.group||'--'}</td><td>${r.country||'--'}</td><td><span class="tier-pill ${tc}">${tier}</span></td><td><span class="badge badge-${cs}" style="font-size:10px">${r.compliance_status||'--'}</span></td><td style="color:${(r.conflict_count||0)>0?'var(--warn)':'var(--muted)'}">${r.conflict_count??'--'}</td><td style="color:${score>=80?'var(--accent)':score>0?'var(--warn)':'var(--danger)'}">${score}%</td>`;
    tbody.appendChild(tr);
  });
}
function filterTable(){
  const tier=document.getElementById('filter-tier').value;
  const comp=document.getElementById('filter-compliance').value;
  fillTable(_allResults.filter(r=>(!tier||r.strategy_tier===tier)&&(!comp||r.compliance_status===comp)));
}
function openDetail(r){document.getElementById('detail-content').innerHTML=renderResultCard(r);document.getElementById('detail-overlay').classList.add('open');}
function closeDetail(){document.getElementById('detail-overlay').classList.remove('open');}


function renderThesisCharts(results) {
  const valid = results.filter(r => r.strategy !== 'ERROR');
  const total = valid.length;
  if (!total) return;

  // ── RQ1: Tier distribution ──────────────────────────────────────────
  const tierCounts = {};
  valid.forEach(r => {
    const t = r.strategy_tier || 'Unknown';
    tierCounts[t] = (tierCounts[t] || 0) + 1;
  });
  const tierColors = {
    'Tier 5': '#ff5c5c', 'Tier 4b': '#4da6ff', 'Tier 4a': '#8338ec',
    'Tier 3': '#00e5a0', 'Tier 2': '#fb8500',  'Tier 1': '#6b7570'
  };
  const tierLabels = Object.keys(tierCounts);
  const tierData   = tierLabels.map(t => tierCounts[t]);
  const tierBg     = tierLabels.map(t => tierColors[t] || '#aaa');

  if (_charts.thesisTier) _charts.thesisTier.destroy();
  _charts.thesisTier = new Chart(document.getElementById('thesis-tier'), {
    type: 'bar',
    data: {
      labels: tierLabels.map(t => {
        const labels = {'Tier 5':'True Nuclear','Tier 4b':'Secured Nuclear',
                        'Tier 4a':'SEO-Captive','Tier 3':'Surgical',
                        'Tier 2':'Porous','Tier 1':'Open'};
        return `${t} — ${labels[t]||''}`;
      }),
      datasets: [{ data: tierData, backgroundColor: tierBg, borderRadius: 4, borderWidth: 0 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b7280', font: { size: 11 } }, grid: { color: 'rgba(0,0,0,0.05)' } },
        y: { ticks: { color: '#374151', font: { size: 12 } }, grid: { display: false } }
      }
    }
  });

  // ── RQ2: Conflict severity ──────────────────────────────────────────
  // Show top sites with conflicts
  const conflicted = valid
    .filter(r => (r.conflict_count || 0) > 0)
    .sort((a, b) => (b.conflict_count || 0) - (a.conflict_count || 0))
    .slice(0, 6);

  const high   = conflicted.map(r => (r.conflicts||[]).filter(c=>c.severity==='HIGH').length);
  const medium = conflicted.map(r => (r.conflicts||[]).filter(c=>c.severity==='MEDIUM').length);
  const low    = conflicted.map(r => (r.conflicts||[]).filter(c=>c.severity==='LOW').length);

  if (_charts.thesisConflicts) _charts.thesisConflicts.destroy();
  _charts.thesisConflicts = new Chart(document.getElementById('thesis-conflicts'), {
    type: 'bar',
    data: {
      labels: conflicted.map(r => r.name || r.url),
      datasets: [
        { label: 'HIGH',   data: high,   backgroundColor: 'rgba(255,92,92,.7)',  borderRadius: 3 },
        { label: 'MEDIUM', data: medium, backgroundColor: 'rgba(255,181,71,.7)', borderRadius: 3 },
        { label: 'LOW',    data: low,    backgroundColor: 'rgba(107,117,112,.5)', borderRadius: 3 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { stacked: true, ticks: { color: '#374151', font: { size: 11 } }, grid: { display: false } },
        y: { stacked: true, ticks: { color: '#6b7280' }, grid: { color: 'rgba(0,0,0,0.05)' } }
      }
    }
  });

  // ── RQ3: Compliance doughnut ────────────────────────────────────────
  const statusCounts = { COMPLIANT: 0, NOMINAL: 0, PARTIAL: 0, NON_COMPLIANT: 0 };
  valid.forEach(r => { statusCounts[r.compliance_status] = (statusCounts[r.compliance_status] || 0) + 1; });

  if (_charts.thesisCompliance) _charts.thesisCompliance.destroy();
  _charts.thesisCompliance = new Chart(document.getElementById('thesis-compliance'), {
    type: 'doughnut',
    data: {
      labels: [
        `Compliant (${statusCounts.COMPLIANT})`,
        `Nominal (${statusCounts.NOMINAL})`,
        `Partial (${statusCounts.PARTIAL})`,
        `Non-compliant (${statusCounts.NON_COMPLIANT})`
      ],
      datasets: [{
        data: [statusCounts.COMPLIANT, statusCounts.NOMINAL, statusCounts.PARTIAL, statusCounts.NON_COMPLIANT],
        backgroundColor: ['#00e5a0', '#ffb547', '#4da6ff', '#ff5c5c'],
        borderWidth: 3, borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '65%',
      plugins: { legend: { display: false } }
    }
  });

  // ── RQ3: Intended vs effective gap bar ─────────────────────────────
  const intended  = valid.filter(r => r.compliance?.intended_optout || r.intended_optout).length;
  const effective = valid.filter(r => r.compliance?.effective_optout || r.effective_optout).length;
  const intendedPct  = Math.round(intended  / total * 100 * 100) / 100;
  const effectivePct = Math.round(effective / total * 100 * 100) / 100;

  if (_charts.thesisGap) _charts.thesisGap.destroy();
  _charts.thesisGap = new Chart(document.getElementById('thesis-gap-bar'), {
    type: 'bar',
    data: {
      labels: [`Intended opt-out (${intendedPct}%)`, `Effective opt-out (${effectivePct}%)`],
      datasets: [{
        data: [intendedPct, effectivePct],
        backgroundColor: ['rgba(77,166,255,.7)', 'rgba(0,229,160,.8)'],
        borderRadius: 4, borderWidth: 0
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { max: 100, ticks: { color: '#6b7280', callback: v => v + '%' }, grid: { color: 'rgba(0,0,0,0.05)' } },
        y: { ticks: { color: '#374151', font: { size: 12 } }, grid: { display: false } }
      }
    }
  });

  // Update the legend rows dynamically
  document.querySelector('#page-thesis .legend-row')?.querySelectorAll('.legend-item').forEach(el => el.remove());
}

function escHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function highlightRobotsLine(raw, conflicts, lineMap) {
  // Build conflict index by line number
  const conflictByLine = {};
  (conflicts || []).forEach(c => {
    if (typeof c.line_number === 'number') conflictByLine[c.line_number] = c;
  });

  return raw.split('\n').map((line, i) => {
    const meta   = lineMap ? lineMap[i] : null;
    const conflict = conflictByLine[i];

    // Row background priority: conflict > relevant block > relevant allow > neutral
    let rowCls = '';
    if (conflict) {
      rowCls = conflict.severity === 'HIGH' ? 'insp-line-high'
             : conflict.severity === 'MEDIUM' ? 'insp-line-med' : 'insp-line-low';
    } else if (meta) {
      if (meta.type === 'disallow' && meta.relevant && meta.severity === 'ok')
        rowCls = 'insp-line-blocked';   // green tint — effective block
      else if (meta.type === 'allow' && meta.relevant)
        rowCls = 'insp-line-allow';     // amber tint — allow for AI bot
      else if (meta.type === 'user-agent' && meta.relevant)
        rowCls = 'insp-line-agent';     // blue tint — relevant agent
    }

    // Conflict marker badge
    let marker = '';
    if (conflict) {
      const cls = conflict.severity === 'HIGH' ? 'insp-mark-high'
                : conflict.severity === 'MEDIUM' ? 'insp-mark-med' : 'insp-mark-low';
      const sym = conflict.severity === 'HIGH' ? '!' : conflict.severity === 'MEDIUM' ? '~' : 'i';
      marker = ` <span class="insp-mark ${cls}" title="${escHtml(conflict.type)} — ${escHtml(conflict.detail||'')}">${sym}</span>`;
    } else if (meta && meta.relevant && meta.type === 'disallow' && meta.severity === 'ok') {
      marker = ` <span class="insp-mark insp-mark-ok" title="Effective AI block">✓</span>`;
    }

    // Syntax colouring
    const t = line.trimStart();
    let html = '';
    if (!t || t.startsWith('#')) {
      html = `<span class="syn-comment">${escHtml(line)}</span>`;
    } else if (t.toLowerCase().startsWith('user-agent:')) {
      const c = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0,c+1))}</span><span class="syn-ua">${escHtml(line.slice(c+1))}</span>`;
    } else if (t.toLowerCase().startsWith('disallow:')) {
      const c = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0,c+1))}</span><span class="syn-dis">${escHtml(line.slice(c+1))}</span>`;
    } else if (t.toLowerCase().startsWith('allow:')) {
      const c = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0,c+1))}</span><span class="syn-allow">${escHtml(line.slice(c+1))}</span>`;
    } else if (t.toLowerCase().startsWith('sitemap:') || t.toLowerCase().startsWith('crawl-delay:')) {
      const c = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0,c+1))}</span><span class="syn-val">${escHtml(line.slice(c+1))}</span>`;
    } else {
      html = `<span class="syn-val">${escHtml(line)}</span>`;
    }

    return `<div class="insp-line ${rowCls}" id="rline-${i}">
      <span class="insp-ln">${i+1}</span>
      <span class="insp-lc">${html}${marker}</span>
    </div>`;
  }).join('');
}