const API = '';

// ── Navigation ───────────────────────────────────────────────────────────────
function showPage(name, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
}

// ── Single URL analysis ──────────────────────────────────────────────────────
async function runSingleAnalysis() {
  let url   = document.getElementById('input-url').value.trim();
  const name  = document.getElementById('input-name').value.trim();
  const group = document.getElementById('input-group').value.trim();
  const btn   = document.getElementById('btn-analyze');
  const spin  = document.getElementById('analyze-spinner');
  const out   = document.getElementById('single-result');
  const errEl = document.getElementById('analyze-error');

  errEl.style.display = 'none';
  if (!url) {
    errEl.textContent = 'Please enter a URL.';
    errEl.style.display = 'block';
    return;
  }

  if (!url.startsWith('http')) url = 'https://' + url;
  try { url = new URL(url).origin; } catch (e) {}

  btn.disabled = true;
  spin.style.display = 'inline-block';
  out.innerHTML = `<div class="info-msg">Fetching robots.txt from <code>${escHtml(url)}</code> …</div>`;

  try {
    const resp = await fetch(API + '/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, name, group }),
    });

    if (!resp.ok) {
      const e = await resp.json().catch(() => ({ error: 'Server error ' + resp.status }));
      throw new Error(e.error || 'Server error ' + resp.status);
    }

    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    out.innerHTML = renderResultCard(data) + renderImprovementAdvisor(data);
  } catch (e) {
    out.innerHTML = `<div class="error-msg">
      <strong>Could not fetch robots.txt.</strong><br><br>
      ${escHtml(e.message)}<br><br>
      <span style="font-size:11px">Common causes: the site blocks automated requests, has no robots.txt,
      or the server timed out. Try just the homepage domain, e.g.
      <code>https://www.bbc.co.uk</code> — do not include paths like /news.</span>
    </div>`;
  } finally {
    btn.disabled = false;
    spin.style.display = 'none';
  }
}

// ── Improvement Advisor ──────────────────────────────────────────────────────
function renderImprovementAdvisor(r) {
  if (r.strategy === 'ERROR') return '';

  const tier   = r.strategy_tier || r.strategy || 'Tier 1';
  const cs     = r.compliance_status || 'NON_COMPLIANT';
  const score  = r.compliance_score || 0;

  // Already at best tier?
  if (tier === 'Tier 5' && cs === 'COMPLIANT') {
    return `<div class="advisor-card advisor-perfect">
      <div class="advisor-header">
        <span class="advisor-icon">&#10003;</span>
        <div>
          <div class="advisor-title">Maximum Protection Active</div>
          <div class="advisor-sub">This configuration is already at the strongest possible tier</div>
        </div>
      </div>
      <p class="advisor-body">Your robots.txt uses a global wildcard block with no exceptions. Every AI crawler — from ChatGPT to infrastructure harvesters — is denied access. There is nothing further to improve from a protection standpoint. The only trade-off is that Googlebot is also blocked, which means this site does not appear in Google Search results. If that is intentional, you are fully protected.</p>
    </div>`;
  }

  if ((tier === 'Tier 4b') && cs === 'COMPLIANT') {
    return `<div class="advisor-card advisor-perfect">
      <div class="advisor-header">
        <span class="advisor-icon">&#10003;</span>
        <div>
          <div class="advisor-title">Near-Maximum Protection — SEO Preserved</div>
          <div class="advisor-sub">Tier 4b (Secured Nuclear) is the optimal tier for sites that need search visibility</div>
        </div>
      </div>
      <p class="advisor-body">You have the best of both worlds: a global wildcard block prevents all AI training crawlers, while an explicit Googlebot exception keeps your content indexed in search. Google-Extended (Gemini training) is also explicitly blocked. This is the recommended configuration for most publishers — full AI protection without sacrificing discoverability.</p>
    </div>`;
  }

  // Build targeted advice based on current tier
  const advice = getImprovementAdvice(r);

  return `<div class="advisor-card">
    <div class="advisor-header">
      <span class="advisor-icon advisor-icon-warn">&#9650;</span>
      <div>
        <div class="advisor-title">How to Improve This Configuration</div>
        <div class="advisor-sub">Currently <strong>${escHtml(tier)}</strong> — ${escHtml(getTierLabel(tier))} &rarr; recommended path below</div>
      </div>
    </div>

    ${renderUpgradePath(tier, cs)}

    <div class="advisor-issues">
      ${advice.map(a => `
        <div class="advisor-issue">
          <div class="advisor-issue-header">
            <span class="advisor-sev advisor-sev-${a.severity}">${escHtml(a.severity)}</span>
            <span class="advisor-issue-title">${escHtml(a.title)}</span>
          </div>
          <p class="advisor-issue-body">${a.body}</p>
          ${a.snippet ? `
            <div class="advisor-snippet-wrap">
              <div class="advisor-snippet-label">Recommended robots.txt addition</div>
              <pre class="advisor-snippet">${escHtml(a.snippet)}</pre>
            </div>` : ''}
        </div>`).join('')}
    </div>

    ${renderBestTierExplainer(tier)}
  </div>`;
}

function getTierLabel(tier) {
  const labels = {
    'Tier 1': 'Open — no AI protection',
    'Tier 2': 'Porous — visible bots only',
    'Tier 3': 'Surgical — named layered blocks',
    'Tier 4a': 'SEO-Captive — Gemini gap',
    'Tier 4b': 'Secured Nuclear — full + SEO',
    'Tier 5': 'True Nuclear — maximum',
  };
  return labels[tier] || tier;
}

function renderUpgradePath(tier, cs) {
  const tiers = ['Tier 1','Tier 2','Tier 3','Tier 4b','Tier 5'];
  const current = tiers.indexOf(tier);
  const target = tier === 'Tier 5' ? 4 : tier === 'Tier 4b' ? 3 : 3; // recommend 4b for most

  const steps = tiers.map((t, i) => {
    const isCurrent = t === tier;
    const isTarget  = t === 'Tier 4b'; // recommended for most
    const isPassed  = i < current;
    const isFuture  = i > current && !isTarget;
    return `<div class="upgrade-step ${isCurrent ? 'step-current' : ''} ${isTarget ? 'step-target' : ''} ${isPassed ? 'step-passed' : ''} ${isFuture ? 'step-future' : ''}">
      <div class="step-dot"></div>
      <div class="step-label">${t}</div>
    </div>`;
  }).join(`<div class="step-connector"></div>`);

  return `<div class="upgrade-path">
    <div class="upgrade-path-label">Protection upgrade path</div>
    <div class="upgrade-steps">${steps}</div>
    <div class="upgrade-legend">
      <span class="leg-current">&#9679; Current</span>
      <span class="leg-target">&#9679; Recommended target</span>
    </div>
  </div>`;
}

function getImprovementAdvice(r) {
  const tier  = r.strategy_tier || r.strategy || 'Tier 1';
  const cs    = r.compliance_status || 'NON_COMPLIANT';
  const conflicts = r.conflicts || [];
  const advice = [];

  // Grab the dynamic backend snippet
  const dynamicFix = r.recommended_robots || "# Replace with Tier 4b rules...";

  // ── NOMINAL: Enumeration Fallacy ──
  if (cs === 'NOMINAL') {
    advice.push({
      severity: 'CRITICAL',
      title: 'Enumeration Fallacy — Your rules are cancelling each other out',
      body: 'You have a wildcard Allow: / directive that overrides all your specific Disallow entries. Under the RFC 9309 parsing rules, when an Allow and Disallow point to the same path with equal specificity, Allow always wins. This means every bot you think you\'ve blocked actually has full access. The fix is to either remove the conflicting Allow: / or restructure the file so per-bot blocks appear inside dedicated sections with no competing Allow.',
      snippet: `# WRONG — Allow: / cancels all Disallow entries below
User-agent: *
Allow: /
Disallow: /

# CORRECT — remove the Allow: / or scope it carefully
User-agent: *
Disallow: /

User-agent: Googlebot
Allow: /`
    });
  }

  // ── Tier 1: no protection at all ──
 if (tier === 'Tier 1') {
    advice.push({
      severity: 'HIGH',
      title: 'No AI crawler protection — all bots have full access',
      body: 'Your robots.txt contains no directives targeting AI training crawlers. Any AI company can freely download and use your content. We have generated a custom Tier 4b Secured Nuclear configuration that preserves your existing structural rules but locks out AI harvesters.',
      snippet: dynamicFix // USE DYNAMIC SNIPPET
    });
  }

  // ── Tier 2: only app layer, missing infra ──
  if (tier === 'Tier 2') {
    advice.push({
      severity: 'HIGH',
      title: 'Infrastructure crawlers are still unblocked',
      body: 'You\'ve blocked the "visible" AI assistants (ChatGPT, ClaudeBot) but the infrastructure-layer harvesters — CCBot, Bytespider, Diffbot, AmazonBot — are still collecting your content. These bots are responsible for building the foundation datasets that train most large models. Blocking GPTBot while leaving CCBot open is like locking the front door but leaving the back window open.',
      snippet: `# Add these to your existing robots.txt

User-agent: CCBot
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: Diffbot
Disallow: /

User-agent: AmazonBot
Disallow: /

User-agent: Omgilibot
Disallow: /

User-agent: Timpibot
Disallow: /

# Or replace all named entries with one wildcard block:
User-agent: *
Disallow: /

User-agent: Googlebot
Allow: /`
    });
  }

  // ── Tier 3: missing Google-Extended ──
if (tier === 'Tier 3') {
    advice.push({
      severity: 'LOW',
      title: 'Consider switching to a wildcard block for long-term reliability',
      body: 'Named bot lists require constant maintenance — new AI crawlers emerge every few months. A global wildcard block combined with an explicit Allow for search indexers future-proofs your site. We have translated your current file into a Secured Nuclear (Tier 4b) setup below.',
      snippet: dynamicFix // USE DYNAMIC SNIPPET
    });
  }

  // ── Tier 4a: has wildcard + Googlebot exception but missing Google-Extended ──
  if (tier === 'Tier 4a') {
    advice.push({
      severity: 'MEDIUM',
      title: 'One directive away from full protection',
      body: 'You have the global wildcard block and the Googlebot exception set up correctly. The only gap is Google-Extended, which is Google\'s AI training crawler. It is completely separate from the regular Googlebot indexer — adding a Disallow for Google-Extended will not affect your search visibility at all. This single addition upgrades you from Tier 4a to Tier 4b.',
      snippet: `# Add these two lines to your existing robots.txt
# (does NOT affect Google Search rankings)

User-agent: Google-Extended
Disallow: /

User-agent: Google-CloudVertexBot
Disallow: /`
    });
  }

  // ── Tier 5: has wildcard but no Googlebot exception ──
  if (tier === 'Tier 5' && cs !== 'COMPLIANT') {
    // NOMINAL case in Tier 5 — conflicts
    advice.push({
      severity: 'HIGH',
      title: 'Directive conflicts are undermining your wildcard block',
      body: 'Your configuration has a global block but internal conflicts are creating exceptions that allow access. Review the conflicts listed above and resolve the contradictions — typically a competing Allow: / that re-grants access after a Disallow: / in the same section.',
    });
  }

  // ── Conflicts present ──
  const highConflicts = conflicts.filter(c => c.severity === 'HIGH');
  if (highConflicts.length > 0 && cs !== 'NOMINAL') {
    advice.push({
      severity: 'HIGH',
      title: `${highConflicts.length} HIGH severity conflict${highConflicts.length > 1 ? 's' : ''} detected`,
      body: 'HIGH severity conflicts mean a specific Allow directive is directly cancelling a Disallow of equal or greater specificity. Under RFC 9309 rules, Allow always wins in a tie. Each HIGH conflict creates a real access path for the exact crawlers you intended to block. Review each conflict shown above and remove the competing Allow directives.',
    });
  }

  const medConflicts = conflicts.filter(c => c.severity === 'MEDIUM');
  if (medConflicts.length > 0) {
    advice.push({
      severity: 'MEDIUM',
      title: `${medConflicts.length} MEDIUM severity conflict${medConflicts.length > 1 ? 's' : ''} — duplicate sections detected`,
      body: 'MEDIUM conflicts are usually duplicate User-agent sections. RFC 9309 requires parsers to merge all sections for the same agent, but some older or non-compliant crawlers may only read the first or last matching section. Consolidate all rules for each User-agent into a single block to eliminate this ambiguity.',
      snippet: `# WRONG — split sections for the same agent
User-agent: GPTBot
Disallow: /news

User-agent: GPTBot
Disallow: /articles

# CORRECT — merge into one section
User-agent: GPTBot
Disallow: /`
    });
  }

  // If no issues found, add positive note
  if (advice.length === 0) {
    advice.push({
      severity: 'INFO',
      title: 'Configuration looks clean — no major issues found',
      body: 'No critical structural problems were detected. Consider periodically reviewing this file as new AI crawlers are introduced — the crawler landscape changes frequently. Check back every few months and compare your User-agent list against the current roster of active AI training bots.',
    });
  }

  return advice;
}

function renderBestTierExplainer(currentTier) {
  return `<div class="tier-explainer">
    <div class="tier-explainer-title">Which tier is right for this site?</div>
    <div class="tier-options">
      <div class="tier-option ${currentTier === 'Tier 5' ? 'tier-option-current' : ''}">
        <div class="tier-option-header">
          <span class="tier-pill tp5">Tier 5</span>
          <span class="tier-option-name">True Nuclear</span>
          <span class="tier-option-tag">Maximum protection</span>
        </div>
        <p>Blocks <em>every</em> crawler including search engines. Your site disappears from Google. Choose this if your content must never be indexed or crawled by anyone — paywalled archives, private databases, or sites whose audience comes from direct traffic only.</p>
      </div>
      <div class="tier-option tier-option-recommended ${currentTier === 'Tier 4b' ? 'tier-option-current' : ''}">
        <div class="tier-option-header">
          <span class="tier-pill tp4b">Tier 4b</span>
          <span class="tier-option-name">Secured Nuclear</span>
          <span class="tier-option-tag tier-option-tag-rec">&#9733; Recommended for most publishers</span>
        </div>
        <p>Blocks all AI training crawlers while keeping Googlebot (and optionally Bingbot) active. You stay visible in search results. Google-Extended is explicitly blocked so Gemini cannot train on your content. This is the optimal balance for the vast majority of news publishers and content sites.</p>
      </div>
      <div class="tier-option ${currentTier === 'Tier 3' ? 'tier-option-current' : ''}">
        <div class="tier-option-header">
          <span class="tier-pill tp3">Tier 3</span>
          <span class="tier-option-name">Surgical</span>
          <span class="tier-option-tag">Targeted — high maintenance</span>
        </div>
        <p>Explicitly names every AI bot you want to block. Effective if kept up-to-date, but new AI crawlers appear frequently. You must check and update your list regularly or new bots will freely access your site. Suitable for technically capable teams who want fine-grained control.</p>
      </div>
      <div class="tier-option ${currentTier === 'Tier 2' ? 'tier-option-current' : ''}">
        <div class="tier-option-header">
          <span class="tier-pill tp2">Tier 2</span>
          <span class="tier-option-name">Porous</span>
          <span class="tier-option-tag tier-option-tag-bad">Not sufficient</span>
        </div>
        <p>Blocks only the "named" AI assistants (ChatGPT, Claude) while leaving infrastructure harvesters (CCBot, Bytespider) unrestricted. These infrastructure bots are responsible for the majority of training data collection. Tier 2 gives an illusion of protection while leaving the most significant exposure open.</p>
      </div>
      <div class="tier-option ${currentTier === 'Tier 1' ? 'tier-option-current' : ''}">
        <div class="tier-option-header">
          <span class="tier-pill tp1">Tier 1</span>
          <span class="tier-option-name">Open</span>
          <span class="tier-option-tag tier-option-tag-bad">No protection</span>
        </div>
        <p>No AI-specific rules exist. Every crawler — training harvesters, AI assistants, scrapers — has unrestricted access to all content. This is the default state when no robots.txt exists or when the file contains no AI-related directives. One addition to your robots.txt file is all that is needed to move out of this tier.</p>
      </div>
    </div>
  </div>`;
}

// ── Result card renderer ─────────────────────────────────────────────────────
function renderResultCard(r) {
  if (r.strategy === 'ERROR') {
    const reason = r.error_type || 'UNKNOWN';
    const hints = {
      '404':     'The site has no robots.txt file at /robots.txt.',
      'timeout': 'The server did not respond in time.',
      'SSL':     'SSL/TLS certificate issue on the remote server.',
    };
    const hint = Object.entries(hints).find(([k]) => reason.includes(k))?.[1]
               || 'The server may be blocking automated requests or the domain is unreachable.';
    return `<div class="result-card">
      <div class="result-header">
        <div>
          <div class="result-site-name">${escHtml(r.name || r.url)}</div>
          <div class="result-url">${escHtml(r.url)}</div>
        </div>
        <span class="badge badge-error">ERROR</span>
      </div>
      <p style="color:var(--danger);font-size:13px;margin-bottom:8px">Failed: ${escHtml(reason)}</p>
      <p style="color:var(--muted);font-size:12px">${escHtml(hint)}</p>
    </div>`;
  }

  const cs    = (r.compliance_status || '').toLowerCase();
  const score = r.compliance_score || 0;
  const pct   = Math.round(score * 100);
  const sc    = pct >= 80 ? 'var(--ok)' : pct >= 40 ? 'var(--warn)' : 'var(--danger)';

  const tierColors = {
    'Tier 5': '#DC2626', 'Tier 4b': '#2563EB', 'Tier 4a': '#7C3AED',
    'Tier 3': '#15803D', 'Tier 2':  '#B45309',  'Tier 1': '#6B7280',
  };
  const tc = tierColors[r.strategy_tier] || '#6B7280';

  const la = r.compliance?.layer_analysis || {};
  const layerData = {
    app_layer:   { effective: r.app_layer_effective   ?? la.app_layer?.effective,   conflict_undermined: la.app_layer?.conflict_undermined },
    infra_layer: { effective: r.infra_layer_effective ?? la.infra_layer?.effective, conflict_undermined: la.infra_layer?.conflict_undermined },
    google_ai:   { effective: r.google_ai_effective   ?? la.google_ai?.effective,   conflict_undermined: la.google_ai?.conflict_undermined },
  };

  const layers = ['app_layer', 'infra_layer', 'google_ai'].map(k => {
    const l   = layerData[k] || {};
    const lbl = { app_layer: 'APP LAYER &middot; 35%', infra_layer: 'INFRA LAYER &middot; 45%', google_ai: 'GOOGLE AI &middot; 20%' }[k];
    return `<div class="layer-cell">
      <div class="layer-name">${lbl}</div>
      <div class="layer-status ${l.effective ? 'layer-effective' : 'layer-ineffective'}">
        ${l.effective ? '&#10003; Blocked' : '&#10007; Exposed'}
      </div>
      ${l.conflict_undermined ? '<div style="font-size:10px;color:var(--danger);margin-top:2px">&#8679; Conflict undermines</div>' : ''}
    </div>`;
  }).join('');

  const sig = r.signal_strength || r.compliance?.signal_strength || 'NONE';
  const sigLabel = { STRONG: 'Strong signal (named AI bot)', WEAK: 'Weak signal (wildcard only)', NONE: 'No opt-out signal' }[sig] || sig;
  const sigColor = sig === 'STRONG' ? 'var(--ok)' : sig === 'WEAK' ? 'var(--warn)' : 'var(--muted)';

  // ── Enhanced "What this means" ──
  const statusExplainer = renderStatusExplainer(r);

  const conflictItems = (r.conflicts || []).slice(0, 8).map(c =>
    `<div class="conflict-item ${c.severity === 'HIGH' ? 'high' : ''}">
      <div class="conflict-type">${escHtml(c.severity)} &middot; ${escHtml(c.type)}</div>
      <div class="conflict-agent">${escHtml(c.affected_agent)}</div>
      <div class="conflict-detail">${escHtml(c.detail || '')}</div>
    </div>`
  ).join('');

  const extraConflicts = (r.conflicts || []).length > 8
    ? `<div style="font-size:11px;color:var(--muted);text-align:center;padding:8px">… and ${r.conflicts.length - 8} more</div>`
    : '';

  const rawSection = r.raw_content ? `
    <div style="margin-top:16px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <div style="font-size:10px;font-family:var(--mono);color:var(--muted);letter-spacing:.08em;text-transform:uppercase">robots.txt — raw content</div>
        <button onclick="toggleRaw(this)" style="font-size:10px;font-family:var(--mono);color:var(--muted);background:none;border:none;cursor:pointer;padding:2px 6px;border-radius:3px;transition:background .1s" onmouseover="this.style.background='var(--surface2)'" onmouseout="this.style.background='none'">&#9660; expand</button>
      </div>
      <div id="raw-body" style="display:none;background:#FEFEFE;border:1px solid var(--border);border-radius:6px;overflow:auto;max-height:380px">
        <pre style="margin:0;padding:6px 0;font-family:var(--mono);font-size:11px;line-height:1.8">${highlightRobotsLines(r.raw_content, r.conflicts || [], r.line_map || {})}</pre>
      </div>
    </div>` : '';

  return `<div class="result-card">
    <div class="result-header">
      <div>
        <div class="result-site-name">${escHtml(r.name || r.url)}</div>
        <div class="result-url">${escHtml(r.url)}</div>
        ${r.redirected ? `<div style="font-size:10px;color:var(--warn);margin-top:3px;font-family:var(--mono)">&#8611; redirected to ${escHtml(r.redirect_target || '')}</div>` : ''}
      </div>
      <span class="badge badge-${cs}">${r.compliance_status || '—'}</span>
    </div>

    <div class="tier-bar">
      <span class="tier-pip" style="background:${tc}"></span>
      <div>
        <div class="tier-text">${escHtml(r.strategy || r.strategy_tier || '')}</div>
        <div class="tier-desc">${escHtml(r.tier_description || r.tier_label || '')}</div>
      </div>
    </div>

    <div class="score-bar-wrap">
      <div class="score-label"><span>Compliance score</span><span style="color:${sc};font-weight:500">${pct}%</span></div>
      <div class="score-track"><div class="score-fill" style="width:${pct}%;background:${sc}"></div></div>
    </div>

    <div class="layers-grid">${layers}</div>

    <div style="margin-bottom:14px;font-size:11px;font-family:var(--mono)">
      <span style="color:var(--hint)">OPT-OUT SIGNAL</span>
      <span style="color:${sigColor};margin-left:8px">${sigLabel}</span>
    </div>

    ${statusExplainer}

    ${(r.conflict_count || 0) > 0
      ? `<div class="conflicts-list">
           <div style="font-size:10px;font-family:var(--mono);color:var(--muted);margin:16px 0 8px;letter-spacing:.06em;text-transform:uppercase">Conflicts (${r.conflict_count})</div>
           ${conflictItems}${extraConflicts}
         </div>`
      : '<div style="margin-top:14px;font-size:12px;color:var(--ok);font-family:var(--mono)">&#10003; No directive conflicts detected</div>'
    }

    <div style="margin-top:16px;padding-top:13px;border-top:1px solid var(--border);font-size:10px;color:var(--hint);font-family:var(--mono)">
      ${escHtml(r.eu_ai_act_ref || r.compliance?.eu_ai_act_ref )}
    </div>

    ${rawSection}
  </div>`;
}

// ── Enhanced status explainer ────────────────────────────────────────────────
function renderStatusExplainer(r) {
  const cs    = r.compliance_status || 'NON_COMPLIANT';
  const tier  = r.strategy_tier || r.strategy || 'Tier 1';
  const score = Math.round((r.compliance_score || 0) * 100);
  const la    = r.compliance?.layer_analysis || {};

  const layerData = {
    app:   r.app_layer_effective   ?? la.app_layer?.effective,
    infra: r.infra_layer_effective ?? la.infra_layer?.effective,
    gai:   r.google_ai_effective   ?? la.google_ai?.effective,
  };

  let cls = 'meaning-box';
  let icon = '';
  let headline = '';
  let body = '';
  let details = [];

  if (cs === 'COMPLIANT') {
    cls = 'meaning-box';
    icon = '&#10003;';
    headline = 'Protection is active and effective';
    body = 'The robots.txt file on this site has been verified as semantically effective. All three crawler categories are blocked and no internal directive conflicts were found that would cancel that protection. A correctly configured robots.txt is the standard machine-readable mechanism for declaring that automated content extraction is not permitted.';
    details = [
      'AI assistants (ChatGPT, Claude, Perplexity) cannot access content',
      'Infrastructure training harvesters (CCBot, Bytespider) are blocked',
      tier === 'Tier 5' ? 'All crawlers including search engines are blocked — site will not appear in Google' : 'Search engine crawlers are still permitted — site remains discoverable',
      'No conflicting Allow directives were found that would re-open access',
    ];
  } else if (cs === 'NOMINAL') {
    cls = 'meaning-box warn';
    icon = '&#9888;';
    headline = 'The Enumeration Fallacy — written rules that do not work';
    body = 'This site has robots.txt entries that look protective on the surface, but they are rendered ineffective by a structural parsing rule. When a robots.txt file contains both an Allow and a Disallow directive pointing to the same path at equal specificity, the Allow directive always wins — this is mandated by the RFC 9309 standard. The result is that this site appears protected but any RFC-compliant crawler (which includes all major AI crawlers) will interpret the file as granting full access.';
    details = [
      'The Disallow entries are present but cancelled by competing Allow directives',
      'Standard binary parsers would classify this site as protected — it is not',
      'A crawler reading this file correctly will see full access permission',
      'The fix requires removing the conflicting Allow directives — see the improvement section below',
    ];
  } else if (cs === 'PARTIAL') {
    cls = 'meaning-box warn';
    icon = '&#9679;';
    headline = `Partial protection — ${score}% of crawler categories blocked`;
    body = `This site blocks some AI crawlers but not all. The compliance score of ${score}% reflects exactly which layers are covered. The layers are weighted by their actual data-harvesting impact: INFRA layer crawlers (worth 45%) are responsible for the majority of training data collection by volume, which is why a site can block ChatGPT and still score below 50% if CCBot is unblocked.`;
    details = [
      `APP layer (GPTBot, ClaudeBot, etc.) — ${layerData.app ? 'BLOCKED ✓' : 'EXPOSED ✗'}`,
      `INFRA layer (CCBot, Bytespider, etc.) — ${layerData.infra ? 'BLOCKED ✓' : 'EXPOSED ✗'}`,
      `Google AI (Google-Extended, etc.) — ${layerData.gai ? 'BLOCKED ✓' : 'EXPOSED ✗'}`,
      'Partial coverage still leaves gaps that training crawlers will use',
    ];
  } else {
    cls = 'meaning-box danger';
    icon = '&#10007;';
    headline = 'No protection — all AI crawlers have full access';
    body = 'This site\'s robots.txt either contains no AI-related directives or is absent entirely. Every AI training crawler — from the "visible" assistants like ChatGPT to the background infrastructure harvesters like CCBot that scrape vast portions of the web — can freely download and index this site\'s content for use in model training. The content published here can be used to train AI models without restriction.';
    details = [
      'AI assistant crawlers (ChatGPT, Claude, Perplexity) have full access',
      'Infrastructure harvesters (CCBot, Bytespider, Diffbot) have full access',
      'Google\'s AI training crawler (Google-Extended) has full access',
      'Adding a single robots.txt rule is enough to change this — see the improvement section below',
    ];
  }

  const detailHtml = details.map(d =>
    `<div class="meaning-detail-item">${escHtml(d)}</div>`
  ).join('');

  return `<div class="${cls}">
    <div class="meaning-header">
      <span class="meaning-icon">${icon}</span>
      <h4>${headline}</h4>
    </div>
    <p>${body}</p>
    ${detailHtml ? `<div class="meaning-details">${detailHtml}</div>` : ''}
  </div>`;
}

// ── Detail drawer ────────────────────────────────────────────────────────────
function openDetail(r) {
  document.getElementById('detail-content').innerHTML =
    renderResultCard(r) + renderImprovementAdvisor(r);
  document.getElementById('detail-overlay').classList.add('open');
}

function closeDetail() {
  document.getElementById('detail-overlay').classList.remove('open');
}

function toggleRaw(btn) {
  const body = document.getElementById('raw-body');
  const expanded = body.style.display === 'block';
  body.style.display = expanded ? 'none' : 'block';
  btn.textContent = expanded ? '▼ expand' : '▲ collapse';
}

// ── robots.txt syntax highlighter ────────────────────────────────────────────
function highlightRobotsLines(raw, conflicts, lineMap) {
  const conflictByLine = {};
  (conflicts || []).forEach(c => {
    if (typeof c.line_number === 'number') conflictByLine[c.line_number] = c;
  });

  return (raw || '').split('\n').map((line, i) => {
    const meta     = lineMap[i] || null;
    const conflict = conflictByLine[i] || null;

    let rowCls = '';
    if (conflict) {
      rowCls = conflict.severity === 'HIGH' ? 'insp-line-high'
             : conflict.severity === 'MEDIUM' ? 'insp-line-med' : 'insp-line-low';
    } else if (meta) {
      if (meta.type === 'disallow' && meta.relevant && meta.severity === 'ok') rowCls = 'insp-line-blocked';
      else if (meta.type === 'allow'      && meta.relevant) rowCls = 'insp-line-allow';
      else if (meta.type === 'user-agent' && meta.relevant) rowCls = 'insp-line-agent';
    }

    let marker = '';
    if (conflict) {
      const cls = conflict.severity === 'HIGH' ? 'insp-mark-high'
                : conflict.severity === 'MEDIUM' ? 'insp-mark-med' : 'insp-mark-low';
      const sym = conflict.severity === 'HIGH' ? '!' : conflict.severity === 'MEDIUM' ? '~' : 'i';
      marker = ` <span class="insp-mark ${cls}" title="${escAttr(conflict.type + ' — ' + (conflict.detail || ''))}">${sym}</span>`;
    } else if (meta && meta.relevant && meta.type === 'disallow' && meta.severity === 'ok') {
      marker = ` <span class="insp-mark insp-mark-ok" title="Effective AI block">&#10003;</span>`;
    }

    const t = line.trimStart();
    let html = '';
    if (!t || t.startsWith('#')) {
      html = `<span class="syn-comment">${escHtml(line)}</span>`;
    } else if (/^user-agent:/i.test(t)) {
      const ci = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0, ci + 1))}</span><span class="syn-ua">${escHtml(line.slice(ci + 1))}</span>`;
    } else if (/^disallow:/i.test(t)) {
      const ci = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0, ci + 1))}</span><span class="syn-dis">${escHtml(line.slice(ci + 1))}</span>`;
    } else if (/^allow:/i.test(t)) {
      const ci = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0, ci + 1))}</span><span class="syn-allow">${escHtml(line.slice(ci + 1))}</span>`;
    } else if (/^(sitemap|crawl-delay):/i.test(t)) {
      const ci = line.indexOf(':');
      html = `<span class="syn-key">${escHtml(line.slice(0, ci + 1))}</span><span class="syn-val">${escHtml(line.slice(ci + 1))}</span>`;
    } else {
      html = `<span class="syn-val">${escHtml(line)}</span>`;
    }

    return `<div class="insp-line ${rowCls}"><span class="insp-ln">${i + 1}</span><span class="insp-lc">${html}${marker}</span></div>`;
  }).join('');
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function escAttr(s) {
  return String(s || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── DOM ready ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('input-url').addEventListener('keydown', e => {
    if (e.key === 'Enter') runSingleAnalysis();
  });
});