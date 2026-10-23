/**
 * Alpha Committee - Web Terminal Client
 */

let state = {
  config: null,
  analyses: [],
  selectedAnalysisId: null,
  activeTranscript: null,
  eventSource: null,
};

// DOM Elements
const el = {
  reportsList: document.getElementById('reportsList'),
  historyCount: document.getElementById('historyCount'),
  searchInput: document.getElementById('searchInput'),
  providerStatusText: document.getElementById('providerStatusText'),
  
  // Hero elements
  heroTicker: document.getElementById('heroTicker'),
  heroDate: document.getElementById('heroDate'),
  heroExecutionTime: document.getElementById('heroExecutionTime'),
  heroDecision: document.getElementById('heroDecision'),
  heroConfidence: document.getElementById('heroConfidence'),
  heroVoteBars: document.getElementById('heroVoteBars'),
  countBuy: document.getElementById('countBuy'),
  countHold: document.getElementById('countHold'),
  countSell: document.getElementById('countSell'),
  statCalls: document.getElementById('statCalls'),
  statTokens: document.getElementById('statTokens'),
  statCost: document.getElementById('statCost'),
  statRounds: document.getElementById('statRounds'),

  // Memo Tab
  memoExecutiveSummary: document.getElementById('memoExecutiveSummary'),
  memoFundamentalView: document.getElementById('memoFundamentalView'),
  memoTechnicalView: document.getElementById('memoTechnicalView'),
  memoSentimentView: document.getElementById('memoSentimentView'),
  memoRiskAssessment: document.getElementById('memoRiskAssessment'),
  memoDevilsAdvocate: document.getElementById('memoDevilsAdvocate'),
  memoPositionSizing: document.getElementById('memoPositionSizing'),
  memoCatalystsList: document.getElementById('memoCatalystsList'),
  memoInvalidationList: document.getElementById('memoInvalidationList'),

  // Round Cards
  round1Cards: document.getElementById('round1Cards'),
  round2Cards: document.getElementById('round2Cards'),
  round3Cards: document.getElementById('round3Cards'),
  toolsAccordion: document.getElementById('toolsAccordion'),

  // Modal & Run Form
  btnNewRun: document.getElementById('btnNewRun'),
  runModal: document.getElementById('runModal'),
  modalCloseBtn: document.getElementById('modalCloseBtn'),
  btnCancelRun: document.getElementById('btnCancelRun'),
  runForm: document.getElementById('runForm'),
  inputSymbol: document.getElementById('inputSymbol'),
  selectProvider: document.getElementById('selectProvider'),
  selectModel: document.getElementById('selectModel'),
  inputPortfolioContext: document.getElementById('inputPortfolioContext'),
  checkDryRun: document.getElementById('checkDryRun'),
  runProgressBox: document.getElementById('runProgressBox'),
  progressStatusText: document.getElementById('progressStatusText'),
  progressFill: document.getElementById('progressFill'),
  progressLogs: document.getElementById('progressLogs'),
  btnSubmitRun: document.getElementById('btnSubmitRun'),
  btnCopyRawJson: document.getElementById('btnCopyRawJson'),
};

// ---------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadConfig();
  await loadAnalysesList();
});

function setupEventListeners() {
  // Tabs Navigation
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      
      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // Search Filter
  el.searchInput.addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    renderAnalysesList(q);
  });

  // Modal open/close
  el.btnNewRun.addEventListener('click', () => openRunModal());
  el.modalCloseBtn.addEventListener('click', () => closeRunModal());
  el.btnCancelRun.addEventListener('click', () => closeRunModal());
  el.runModal.addEventListener('click', (e) => {
    if (e.target === el.runModal) closeRunModal();
  });

  // Provider change in modal updates models
  el.selectProvider.addEventListener('change', () => updateModelDropdown());

  // Quick ticker chips
  document.querySelectorAll('.quick-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      el.inputSymbol.value = chip.dataset.ticker;
    });
  });

  // Form Submission
  el.runForm.addEventListener('submit', handleRunSubmit);

  // Copy Raw JSON
  el.btnCopyRawJson.addEventListener('click', () => {
    if (!state.activeTranscript) return;
    navigator.clipboard.writeText(JSON.stringify(state.activeTranscript, null, 2));
    const origText = el.btnCopyRawJson.innerText;
    el.btnCopyRawJson.innerText = 'Copied to Clipboard!';
    setTimeout(() => { el.btnCopyRawJson.innerText = origText; }, 2000);
  });
}

// ---------------------------------------------------------------------
// Data Fetching
// ---------------------------------------------------------------------
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    state.config = await res.json();
    
    // Status text
    const geminiActive = state.config.providers.gemini.has_key;
    const anthropicActive = state.config.providers.anthropic.has_key;
    
    if (geminiActive && anthropicActive) {
      el.providerStatusText.innerText = 'Gemini & Claude Active';
    } else if (geminiActive) {
      el.providerStatusText.innerText = 'Google Gemini Active';
    } else if (anthropicActive) {
      el.providerStatusText.innerText = 'Anthropic Claude Active';
    } else {
      el.providerStatusText.innerText = 'Simulation Mode (No Keys)';
    }

    updateModelDropdown();
  } catch (err) {
    console.error('Failed to load system config:', err);
  }
}

function updateModelDropdown() {
  if (!state.config) return;
  const provider = el.selectProvider.value;
  const providerInfo = state.config.providers[provider];
  if (!providerInfo) return;

  el.selectModel.innerHTML = '';
  providerInfo.models.forEach(modelName => {
    const opt = document.createElement('option');
    opt.value = modelName;
    opt.innerText = modelName + (modelName === providerInfo.default_model ? ' (Default)' : '');
    el.selectModel.appendChild(opt);
  });
}

async function loadAnalysesList() {
  try {
    const res = await fetch('/api/analyses');
    const data = await res.json();
    state.analyses = data.analyses || [];
    el.historyCount.innerText = state.analyses.length;
    renderAnalysesList();

    if (state.analyses.length > 0) {
      loadAnalysisDetail(state.analyses[0].id);
    }
  } catch (err) {
    el.reportsList.innerHTML = `<div class="loading-state text-rose">Error loading history: ${err.message}</div>`;
  }
}

function renderAnalysesList(filterText = '') {
  el.reportsList.innerHTML = '';
  const filtered = state.analyses.filter(a => 
    !filterText || a.symbol.toLowerCase().includes(filterText)
  );

  if (filtered.length === 0) {
    el.reportsList.innerHTML = '<div class="loading-state">No matching analyses found.</div>';
    return;
  }

  filtered.forEach(analysis => {
    const item = document.createElement('div');
    item.className = `report-item ${analysis.id === state.selectedAnalysisId ? 'active' : ''}`;
    
    const decisionLower = (analysis.decision || 'hold').toLowerCase();
    const dateFormatted = analysis.started_at 
      ? new Date(analysis.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      : 'Recent';

    item.innerHTML = `
      <div class="item-top">
        <span class="item-ticker">${analysis.symbol}</span>
        <span class="decision-tag ${decisionLower}">${analysis.decision}</span>
      </div>
      <div class="item-bottom">
        <span>${dateFormatted}</span>
        <span>${analysis.confidence ? Math.round(analysis.confidence * 100) + '%' : ''} • $${Number(analysis.total_cost_usd || 0).toFixed(4)}</span>
      </div>
    `;

    item.addEventListener('click', () => {
      loadAnalysisDetail(analysis.id);
    });

    el.reportsList.appendChild(item);
  });
}

async function loadAnalysisDetail(id) {
  state.selectedAnalysisId = id;
  renderAnalysesList(el.searchInput.value.trim().toLowerCase());

  try {
    const res = await fetch(`/api/analyses/${encodeURIComponent(id)}`);
    if (!res.ok) throw new Error('Analysis not found');
    const transcript = await res.json();
    state.activeTranscript = transcript;
    renderAnalysisView(transcript);
  } catch (err) {
    console.error('Error fetching analysis detail:', err);
  }
}

// ---------------------------------------------------------------------
// Rendering Details
// ---------------------------------------------------------------------
function renderAnalysisView(t) {
  const symbol = t.symbol || 'N/A';
  const chairMemo = t.rounds?.final_chair_memo?.output || {};
  const usage = t.usage || {};
  const tally = t.vote_tally || { buy: 0, hold: 0, sell: 0 };
  
  // Hero overview
  el.heroTicker.innerText = symbol;
  el.heroDate.innerText = t.started_at ? new Date(t.started_at).toLocaleString() : 'N/A';
  
  if (t.started_at && t.finished_at) {
    const durSec = ((new Date(t.finished_at) - new Date(t.started_at)) / 1000).toFixed(1);
    el.heroExecutionTime.innerText = `Duration: ${durSec}s`;
  } else {
    el.heroExecutionTime.innerText = '';
  }

  const decision = (chairMemo.decision || 'HOLD').toUpperCase();
  el.heroDecision.innerText = decision;
  el.heroDecision.className = `decision-badge ${decision.toLowerCase()}`;

  const conf = chairMemo.confidence ? Math.round(chairMemo.confidence * 100) : 0;
  el.heroConfidence.innerText = `${conf}%`;

  // Vote bar calculations
  const totalVotes = (tally.buy || 0) + (tally.hold || 0) + (tally.sell || 0) || 1;
  const buyPct = Math.round(((tally.buy || 0) / totalVotes) * 100);
  const holdPct = Math.round(((tally.hold || 0) / totalVotes) * 100);
  const sellPct = 100 - buyPct - holdPct;

  el.heroVoteBars.innerHTML = `
    <div class="vote-bar-fill buy-fill" style="width: ${buyPct}%">${tally.buy || 0} Buy</div>
    <div class="vote-bar-fill hold-fill" style="width: ${holdPct}%">${tally.hold || 0} Hold</div>
    <div class="vote-bar-fill sell-fill" style="width: ${sellPct}%">${tally.sell || 0} Sell</div>
  `;
  el.countBuy.innerText = tally.buy || 0;
  el.countHold.innerText = tally.hold || 0;
  el.countSell.innerText = tally.sell || 0;

  // Stats
  el.statCalls.innerText = usage.total_calls || 12;
  el.statTokens.innerText = `${((usage.total_input_tokens || 0) + (usage.total_output_tokens || 0)).toLocaleString()}`;
  el.statCost.innerText = `$${Number(usage.total_cost_usd || 0).toFixed(4)}`;

  // Tab 1: Final Decision Memo
  el.memoExecutiveSummary.innerText = chairMemo.executive_summary || 'No summary available.';
  el.memoFundamentalView.innerText = chairMemo.fundamental_view || 'N/A';
  el.memoTechnicalView.innerText = chairMemo.technical_view || 'N/A';
  el.memoSentimentView.innerText = chairMemo.sentiment_view || 'N/A';
  el.memoRiskAssessment.innerText = chairMemo.risk_assessment || 'N/A';
  el.memoDevilsAdvocate.innerText = chairMemo.devils_advocate_challenge || 'N/A';
  el.memoPositionSizing.innerText = chairMemo.recommended_position_sizing || 'Standard sizing recommended.';

  renderListItems(el.memoCatalystsList, chairMemo.key_catalysts_to_watch);
  renderListItems(el.memoInvalidationList, chairMemo.invalidation_conditions);

  // Tab 2: Round 1 Specialists
  renderRound1(t.rounds?.round1_analysts || []);

  // Tab 3: Round 2 Risk & Devil
  renderRound2(t.rounds?.round2_risk_devil || []);

  // Tab 4: Round 3 Rebuttals
  renderRound3(t.rounds?.round3_rebuttals || []);

  // Tab 5: Tools Accordion
  renderToolsAccordion(t);
}

function renderListItems(listEl, items) {
  listEl.innerHTML = '';
  if (!items || !items.length) {
    listEl.innerHTML = '<li>None identified</li>';
    return;
  }
  items.forEach(item => {
    const li = document.createElement('li');
    li.innerText = item;
    listEl.appendChild(li);
  });
}

function renderRound1(analysts) {
  el.round1Cards.innerHTML = '';
  analysts.forEach(a => {
    const out = a.output || {};
    const card = document.createElement('div');
    const roleType = a.agent.includes('fundamental') ? 'fundamental' : (a.agent.includes('technical') ? 'technical' : 'sentiment');
    card.className = `card glass-panel specialist-card ${roleType}`;

    const rating = (out.rating || 'hold').toUpperCase();
    const conf = out.confidence ? Math.round(out.confidence * 100) : 0;
    const title = formatRoleTitle(a.agent);

    card.innerHTML = `
      <div class="specialist-header">
        <div>
          <div class="specialist-title">${title}</div>
          <div class="specialist-role">Specialist Report &bull; Round 1</div>
        </div>
        <span class="decision-tag ${rating.toLowerCase()}">${rating} (${conf}%)</span>
      </div>
      <p style="color: #cbd5e1; font-size: 13px; line-height: 1.6;">${out.summary || ''}</p>
      
      ${renderCustomMetrics(out)}

      <div class="points-section">
        <span class="points-title text-emerald">Bull Points</span>
        <ul class="styled-list emerald-check">
          ${(out.bull_points || []).map(p => `<li>${p}</li>`).join('')}
        </ul>
      </div>

      <div class="points-section">
        <span class="points-title text-rose">Bear Points</span>
        <ul class="styled-list rose-cross">
          ${(out.bear_points || []).map(p => `<li>${p}</li>`).join('')}
        </ul>
      </div>
    `;

    el.round1Cards.appendChild(card);
  });
}

function renderCustomMetrics(out) {
  if (out.signals) {
    return `
      <div style="background: rgba(0,0,0,0.25); padding: 10px; border-radius: 6px; font-size: 12px; font-family: var(--font-mono);">
        <div><strong>Trend:</strong> ${out.signals.trend || 'N/A'}</div>
        <div><strong>RSI:</strong> ${out.signals.rsi_signal || 'N/A'}</div>
        <div><strong>MACD:</strong> ${out.signals.macd_signal || 'N/A'}</div>
      </div>
    `;
  }
  if (out.key_metrics) {
    return `
      <div style="background: rgba(0,0,0,0.25); padding: 10px; border-radius: 6px; font-size: 12px;">
        <div><strong>Valuation:</strong> ${out.key_metrics.valuation_assessment || 'N/A'}</div>
        <div><strong>Profitability:</strong> ${out.key_metrics.profitability_assessment || 'N/A'}</div>
      </div>
    `;
  }
  return '';
}

function renderRound2(challengers) {
  el.round2Cards.innerHTML = '';
  challengers.forEach(c => {
    const out = c.output || {};
    const card = document.createElement('div');
    const isRisk = c.agent.includes('risk');
    card.className = `card glass-panel specialist-card ${isRisk ? 'risk' : 'devil'}`;

    const vote = (out.vote || 'hold').toUpperCase();
    const title = formatRoleTitle(c.agent);

    card.innerHTML = `
      <div class="specialist-header">
        <div>
          <div class="specialist-title">${title}</div>
          <div class="specialist-role">Stress Test & Challenge &bull; Round 2</div>
        </div>
        <span class="decision-tag ${vote.toLowerCase()}">${vote}</span>
      </div>
      
      <div>
        <h5 style="color: #fff; margin-bottom: 6px;">${isRisk ? 'Risk Evaluation' : 'Counter-Thesis Challenge'}</h5>
        <p style="color: #cbd5e1; font-size: 13px; line-height: 1.6;">${out.summary || out.thesis_challenge || ''}</p>
      </div>

      ${out.position_sizing_guidance ? `
        <div class="highlight-box">
          <strong>Position Sizing Guidance:</strong> ${out.position_sizing_guidance}
        </div>
      ` : ''}

      ${out.key_risks ? `
        <div class="points-section">
          <span class="points-title text-rose">Identified Risks</span>
          <ul class="styled-list rose-cross">
            ${out.key_risks.map(r => `<li>${r}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      ${out.blind_spots ? `
        <div class="points-section">
          <span class="points-title text-amber">Blind Spots & Traps</span>
          <ul class="styled-list">
            ${out.blind_spots.map(b => `<li>${b}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    `;

    el.round2Cards.appendChild(card);
  });
}

function renderRound3(rebuttals) {
  el.round3Cards.innerHTML = '';
  rebuttals.forEach(r => {
    const out = r.output || {};
    const card = document.createElement('div');
    card.className = 'card glass-panel specialist-card';

    const rating = (out.rating || 'hold').toUpperCase();
    const conf = out.confidence ? Math.round(out.confidence * 100) : 0;
    const title = formatRoleTitle(r.agent);

    card.innerHTML = `
      <div class="specialist-header">
        <div>
          <div class="specialist-title">${title} Rebuttal</div>
          <div class="specialist-role">Defense & Thesis Revision &bull; Round 3</div>
        </div>
        <span class="decision-tag ${rating.toLowerCase()}">${rating} (${conf}%)</span>
      </div>

      <p style="color: #cbd5e1; font-size: 13px; line-height: 1.6;">${out.rebuttal_summary || ''}</p>

      ${out.response_to_devils_advocate ? `
        <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px;">
          <strong style="color: #38bdf8;">Response to Devil's Advocate:</strong>
          <p style="font-size: 12px; color: #94a3b8; margin-top: 4px;">${out.response_to_devils_advocate}</p>
        </div>
      ` : ''}

      ${out.concessions_made ? `
        <div class="points-section">
          <span class="points-title text-amber">Concessions / Revised Caveats</span>
          <ul class="styled-list">
            ${(out.concessions_made || []).map(c => `<li>${c}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    `;

    el.round3Cards.appendChild(card);
  });
}

function renderToolsAccordion(t) {
  el.toolsAccordion.innerHTML = '';
  const analysts = t.rounds?.round1_analysts || [];
  let toolCount = 0;

  analysts.forEach(a => {
    const msgs = a.messages || [];
    msgs.forEach((m, idx) => {
      if (m.role === 'user' && Array.isArray(m.content)) {
        m.content.forEach(c => {
          if (c.type === 'tool_result' || c.content) {
            toolCount++;
            let parsedContent = c.content;
            try {
              if (typeof parsedContent === 'string') {
                parsedContent = JSON.parse(parsedContent);
              }
            } catch (e) { /* keep as string */ }

            const accItem = document.createElement('div');
            accItem.className = 'accordion-item';
            accItem.innerHTML = `
              <div class="accordion-trigger">
                <div>
                  <span class="accordion-tool-name">${formatRoleTitle(a.agent)}: Tool Result</span>
                  <span style="font-size: 11px; color: var(--text-dim); margin-left: 10px;">ID: ${c.tool_use_id || 'tool-call'}</span>
                </div>
                <span>▼</span>
              </div>
              <div class="accordion-content">
                <pre>${JSON.stringify(parsedContent, null, 2)}</pre>
              </div>
            `;

            accItem.querySelector('.accordion-trigger').addEventListener('click', () => {
              accItem.classList.toggle('open');
            });

            el.toolsAccordion.appendChild(accItem);
          }
        });
      }
    });
  });

  if (toolCount === 0) {
    el.toolsAccordion.innerHTML = '<div style="color: var(--text-dim); font-size: 13px;">No raw tool execution blocks available in this transcript.</div>';
  }
}

function formatRoleTitle(name) {
  if (!name) return 'Specialist';
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}

// ---------------------------------------------------------------------
// Modal & Live Committee Run Controller
// ---------------------------------------------------------------------
function openRunModal() {
  el.runModal.classList.add('open');
  el.inputSymbol.focus();
  el.runProgressBox.style.display = 'none';
  el.btnSubmitRun.disabled = false;
  el.progressLogs.innerHTML = '';
  el.progressFill.style.width = '5%';
  document.querySelectorAll('.stage-step').forEach(s => s.className = 'stage-step');

  // Pre-check simulation mode if no live keys found
  const hasGeminiKey = state.config?.providers?.gemini?.has_key;
  const hasAnthropicKey = state.config?.providers?.anthropic?.has_key;
  if (!hasGeminiKey && !hasAnthropicKey) {
    el.checkDryRun.checked = true;
  }
}

function closeRunModal() {
  el.runModal.classList.remove('open');
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
}

async function handleRunSubmit(e) {
  e.preventDefault();
  const symbol = el.inputSymbol.value.trim().toUpperCase();
  if (!symbol) return;

  const provider = el.selectProvider.value;
  const model = el.selectModel.value;
  const portfolio_context = el.inputPortfolioContext.value.trim();
  const dry_run = el.checkDryRun.checked;

  el.btnSubmitRun.disabled = true;
  el.runProgressBox.style.display = 'block';
  el.progressStatusText.innerText = `Submitting deliberation job for ${symbol}...`;

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol,
        provider,
        model,
        portfolio_context,
        dry_run,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start committee run');
    }

    const data = await res.json();
    connectToJobStream(data.job_id);
  } catch (err) {
    el.progressStatusText.innerText = `Error: ${err.message}`;
    el.btnSubmitRun.disabled = false;
  }
}

function connectToJobStream(jobId) {
  if (state.eventSource) {
    state.eventSource.close();
  }

  const sse = new EventSource(`/api/jobs/${jobId}/stream`);
  state.eventSource = sse;

  sse.onmessage = (event) => {
    if (event.data === '[DONE]') {
      sse.close();
      return;
    }

    try {
      const msg = JSON.parse(event.data);
      handleStreamMessage(msg);
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  };

  sse.onerror = (err) => {
    console.error('SSE connection error:', err);
    sse.close();
  };
}

function handleStreamMessage(msg) {
  const logDiv = document.createElement('div');
  logDiv.innerText = msg.message || msg.error || JSON.stringify(msg);
  el.progressLogs.appendChild(logDiv);
  el.progressLogs.scrollTop = el.progressLogs.scrollHeight;

  if (msg.type === 'stage') {
    el.progressStatusText.innerText = msg.message;
    if (msg.stage === 'round1') {
      el.progressFill.style.width = '25%';
      document.getElementById('stage-round1').className = 'stage-step active';
    } else if (msg.stage === 'round2') {
      el.progressFill.style.width = '50%';
      document.getElementById('stage-round1').className = 'stage-step done';
      document.getElementById('stage-round2').className = 'stage-step active';
    } else if (msg.stage === 'round3') {
      el.progressFill.style.width = '75%';
      document.getElementById('stage-round2').className = 'stage-step done';
      document.getElementById('stage-round3').className = 'stage-step active';
    } else if (msg.stage === 'final') {
      el.progressFill.style.width = '90%';
      document.getElementById('stage-round3').className = 'stage-step done';
      document.getElementById('stage-final').className = 'stage-step active';
    }
  } else if (msg.type === 'complete') {
    el.progressFill.style.width = '100%';
    document.getElementById('stage-final').className = 'stage-step done';
    el.progressStatusText.innerText = `Committee deliberation for ${msg.symbol} finished with decision: ${msg.decision}!`;

    setTimeout(async () => {
      closeRunModal();
      await loadAnalysesList();
      if (msg.filename) {
        await loadAnalysisDetail(msg.filename);
      }
    }, 1200);
  } else if (msg.type === 'error') {
    el.progressStatusText.innerText = `Deliberation Error: ${msg.error}`;
    el.btnSubmitRun.disabled = false;
  }
}
