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
    renderDashboard(_allResults,data.metrics||{});
  }catch(e){alert('Batch error: '+e.message);}
  finally{btn.disabled=false;spin.style.display='none';}
}

function loadDemoData(){
  const M={total_sites:81,compliant:69,partial:0,nominal:2,non_compliant:10,compliance_gap:12,gap_percentage:14.81,intended_rate:87.65,effective_rate:85.19,enumeration_fallacy_count:2};
  const R=[
    {name:'Dagens Nyheter',group:'Bonnier',country:'SE',strategy_tier:'Tier 3',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:1,tier_label:'Surgical'},
    {name:'Expressen',group:'Bonnier',country:'SE',strategy_tier:'Tier 3',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'Surgical'},
    {name:'Helsingborgs Dagblad',group:'Bonnier',country:'SE',strategy_tier:'Tier 5',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'True Nuclear'},
    {name:'Mitti Stockholm',group:'Bonnier',country:'SE',strategy_tier:'Tier 1',compliance_status:'NON_COMPLIANT',compliance_score:0.0,conflict_count:0,tier_label:'Open'},
    {name:'Aftonbladet',group:'Schibsted',country:'SE',strategy_tier:'Tier 5',compliance_status:'NOMINAL',compliance_score:0.0,conflict_count:35,tier_label:'True Nuclear'},
    {name:'Svenska Dagbladet',group:'Schibsted',country:'SE',strategy_tier:'Tier 5',compliance_status:'NOMINAL',compliance_score:0.0,conflict_count:35,tier_label:'True Nuclear'},
    {name:'Omni',group:'Schibsted',country:'SE',strategy_tier:'Tier 1',compliance_status:'NON_COMPLIANT',compliance_score:0.0,conflict_count:0,tier_label:'Open'},
    {name:'Klart.se',group:'Schibsted',country:'SE',strategy_tier:'Tier 1',compliance_status:'NON_COMPLIANT',compliance_score:0.0,conflict_count:0,tier_label:'Open'},
    {name:'Tv.nu',group:'Schibsted',country:'SE',strategy_tier:'Tier 3',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'Surgical'},
    {name:'Norrköpings Tidningar',group:'NTM',country:'SE',strategy_tier:'Tier 4b',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:24,tier_label:'Secured Nuclear'},
    {name:'Upsala Nya Tidning',group:'NTM',country:'SE',strategy_tier:'Tier 4b',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:24,tier_label:'Secured Nuclear'},
    {name:'Göteborgs-Posten',group:'Stampen',country:'SE',strategy_tier:'Tier 5',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'True Nuclear'},
    {name:'Jönköpings-Posten',group:'Hall Media',country:'SE',strategy_tier:'Tier 5',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'True Nuclear'},
    {name:'SVT Nyheter',group:'Public Service',country:'SE',strategy_tier:'Tier 3',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'Surgical'},
    {name:'Sveriges Radio',group:'Public Service',country:'SE',strategy_tier:'Tier 3',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'Surgical'},
    {name:'UR',group:'Public Service',country:'SE',strategy_tier:'Tier 1',compliance_status:'NON_COMPLIANT',compliance_score:0.0,conflict_count:0,tier_label:'Open'},
    {name:'Dagens ETC',group:'Independent',country:'SE',strategy_tier:'Tier 1',compliance_status:'NON_COMPLIANT',compliance_score:0.0,conflict_count:0,tier_label:'Open'},
    {name:'Samnytt',group:'Independent',country:'SE',strategy_tier:'Tier 1',compliance_status:'NON_COMPLIANT',compliance_score:0.0,conflict_count:0,tier_label:'Open'},
    {name:'Norra Skane',group:'Independent',country:'SE',strategy_tier:'Tier 3',compliance_status:'COMPLIANT',compliance_score:1.0,conflict_count:0,tier_label:'Surgical'},
  ];
  _allResults=R;renderTable(R);renderDashboard(R,M);
}

function renderTable(results){
  document.getElementById('results-empty').style.display='none';
  document.getElementById('results-table-wrap').style.display='block';
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
    const tc=tier==='Tier 5'?'tp5':tier==='Tier 4b'?'tp4b':tier==='Tier 3'?'tp3':'tp1';
    const cs=(r.compliance_status||'').toLowerCase();
    const score=Math.round((r.compliance_score||0)*100);
    tr.innerHTML=`<td class="name-col">${r.name}</td><td>${r.group||'--'}</td><td>${r.country||'--'}</td><td><span class="tier-pill ${tc}">${tier}</span></td><td><span class="badge badge-${cs}" style="font-size:10px">${r.compliance_status||'--'}</span></td><td style="color:${(r.conflict_count||0)>0?'var(--warn)':'var(--muted)'}">${r.conflict_count??'--'}</td><td style="color:${score>=80?'var(--accent)':score>0?'var(--warn)':'var(--danger)'}">${score}%</td>`;
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

function renderDashboard(results,m){
  document.getElementById('dashboard-empty').style.display='none';
  document.getElementById('dashboard-content').style.display='block';
  const total=m.total_sites||results.length;
  const cp=total?Math.round((m.compliant/total)*100):0;
  document.getElementById('metrics-row').innerHTML=`
    <div class="metric-card"><div class="m-label">Sites analyzed</div><div class="m-value">${total}</div></div>
    <div class="metric-card"><div class="m-label">Compliant</div><div class="m-value" style="color:var(--accent)">${cp}%</div><div class="m-sub">${m.compliant||0} / ${total}</div></div>
    <div class="metric-card"><div class="m-label">Compliance gap</div><div class="m-value" style="color:var(--danger)">${(m.gap_percentage||0).toFixed(1)}%</div><div class="m-sub">${m.compliance_gap||0} sites</div></div>
    <div class="metric-card"><div class="m-label">Enum. Fallacy</div><div class="m-value" style="color:var(--warn)">${m.enumeration_fallacy_count||0}</div><div class="m-sub">NOMINAL sites</div></div>`;
  const gc='rgba(255,255,255,0.05)';const tc='#6b7570';
  const tierC={};results.forEach(r=>{if(r.strategy_tier&&r.strategy_tier!=='ERROR')tierC[r.strategy_tier]=(tierC[r.strategy_tier]||0)+1;});
  const tclr={'Tier 5':'#ff5c5c','Tier 4b':'#4da6ff','Tier 4a':'#8338ec','Tier 3':'#00e5a0','Tier 2':'#fb8500','Tier 1':'#6b7570'};
  if(_charts.tier)_charts.tier.destroy();
  _charts.tier=new Chart(document.getElementById('chart-tier'),{type:'doughnut',data:{labels:Object.keys(tierC),datasets:[{data:Object.values(tierC),backgroundColor:Object.keys(tierC).map(t=>tclr[t]||'#444'),borderWidth:2,borderColor:'#0d0f0e'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}});
  const grps={};results.forEach(r=>{if(!r.group)return;if(!grps[r.group])grps[r.group]={c:0,n:0,nc:0};if(r.compliance_status==='COMPLIANT')grps[r.group].c++;else if(r.compliance_status==='NOMINAL')grps[r.group].n++;else if(r.compliance_status==='NON_COMPLIANT')grps[r.group].nc++;});
  const gl=Object.keys(grps);
  if(_charts.group)_charts.group.destroy();
  _charts.group=new Chart(document.getElementById('chart-group'),{type:'bar',data:{labels:gl,datasets:[{label:'Compliant',data:gl.map(g=>grps[g].c),backgroundColor:'#00e5a0'},{label:'Nominal',data:gl.map(g=>grps[g].n),backgroundColor:'#ffb547'},{label:'Non-compliant',data:gl.map(g=>grps[g].nc),backgroundColor:'#ff5c5c'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{stacked:true,ticks:{color:tc,font:{size:10}},grid:{color:gc}},y:{stacked:true,ticks:{color:tc},grid:{color:gc}}}}});
  if(_charts.comp)_charts.comp.destroy();
  _charts.comp=new Chart(document.getElementById('chart-compliance'),{type:'doughnut',data:{labels:['Compliant','Nominal','Non-compliant'],datasets:[{data:[m.compliant||69,m.nominal||2,m.non_compliant||10],backgroundColor:['#00e5a0','#ffb547','#ff5c5c'],borderWidth:2,borderColor:'#0d0f0e'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}});
  if(_charts.intent)_charts.intent.destroy();
  _charts.intent=new Chart(document.getElementById('chart-intent'),{type:'bar',data:{labels:['Intended opt-out','Effective opt-out'],datasets:[{data:[m.intended_rate||87.65,m.effective_rate||85.19],backgroundColor:['#4da6ff','#00e5a0'],borderRadius:4,borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{max:100,ticks:{color:tc,callback:v=>v+'%'},grid:{color:gc}},y:{ticks:{color:tc,font:{size:11}},grid:{display:false}}}}});
}

function initThesisCharts(){
  new Chart(document.getElementById('thesis-tier'),{type:'bar',data:{labels:['Tier 3 -- Surgical','Tier 5 -- True Nuclear','Tier 4b -- Secured Nuclear','Tier 1 -- Open'],datasets:[{data:[30,27,14,10],backgroundColor:['#00e5a0','#ff5c5c','#4da6ff','#6b7570'],borderRadius:4,borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#6b7570',font:{size:11}},grid:{color:'rgba(255,255,255,0.05)'}},y:{ticks:{color:'#e8ede9',font:{size:12}},grid:{display:false}}}}});
  new Chart(document.getElementById('thesis-conflicts'),{type:'bar',data:{labels:['Aftonbladet','Svenska Dagbladet','NTM (14 sites)','Dagens Nyheter'],datasets:[{label:'HIGH',data:[35,35,0,0],backgroundColor:'rgba(255,92,92,.7)',borderRadius:3},{label:'MEDIUM',data:[0,0,24,0],backgroundColor:'rgba(255,181,71,.7)',borderRadius:3},{label:'LOW',data:[0,0,0,1],backgroundColor:'rgba(107,117,112,.5)',borderRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{stacked:true,ticks:{color:'#e8ede9',font:{size:12}},grid:{display:false}},y:{stacked:true,ticks:{color:'#6b7570'},grid:{color:'rgba(255,255,255,0.05)'}}}}});
  new Chart(document.getElementById('thesis-compliance'),{type:'doughnut',data:{labels:['Compliant (69)','Non-compliant (10)','Nominal (2)'],datasets:[{data:[69,10,2],backgroundColor:['#00e5a0','#ff5c5c','#ffb547'],borderWidth:3,borderColor:'#0d0f0e'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},cutout:'65%'}});
  new Chart(document.getElementById('thesis-gap-bar'),{type:'bar',data:{labels:['Intended opt-out (87.65%)','Effective opt-out (85.19%)'],datasets:[{data:[87.65,85.19],backgroundColor:['rgba(77,166,255,.6)','rgba(0,229,160,.7)'],borderRadius:4,borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{max:100,ticks:{color:'#6b7570',callback:v=>v+'%'},grid:{color:'rgba(255,255,255,0.05)'}},y:{ticks:{color:'#e8ede9',font:{size:12}},grid:{display:false}}}}});
}

initThesisCharts();
