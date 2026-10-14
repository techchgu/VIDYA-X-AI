/* ============================================================
   VIDYA-X AI — Evaluation Dashboard JS (Step 13)
   evaluation.js — Vanilla ES2020, no frameworks
   ============================================================ */

'use strict';

const API = 'http://localhost:8000';

// ── DOM refs ────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// Run controls
const triggerRunBtn      = $('triggerRunBtn');
const taskTypeSelect     = $('taskTypeSelect');
const datasetVersionInput = $('datasetVersionInput');
const maxCasesInput      = $('maxCasesInput');
const deterministicOnly  = $('deterministicOnly');
const runStatusEl        = $('runStatus');

// Runs list
const runsLoadingEl   = $('runsLoading');
const runsEmptyEl     = $('runsEmpty');
const runsErrorEl     = $('runsError');
const runsTableEl     = $('runsTable');
const runsTableBody   = $('runsTableBody');
const refreshRunsBtn  = $('refreshRunsBtn');

// Run detail
const runDetailEl       = $('runDetail');
const qualityGateBanner = $('qualityGateBanner');
const metricCategoryCards = $('metricCategoryCards');
const metricsLoadingEl  = $('metricsLoading');
const metricsErrorEl    = $('metricsError');
const metricsTableWrap  = $('metricsTableWrap');
const metricsTableBody  = $('metricsTableBody');
const metricSampleNote  = $('metricSampleNote');
const casesLoadingEl    = $('casesLoading');
const casesErrorEl      = $('casesError');
const casesTableWrap    = $('casesTableWrap');
const casesTableBody    = $('casesTableBody');
const casesCountEl      = $('casesCount');
const runMetadataPre    = $('runMetadataPre');

// Case filters
const caseFilterStatus  = $('caseFilterStatus');
const caseFilterType    = $('caseFilterType');

// ── State ───────────────────────────────────────────────────
let currentRunId  = null;
let allCases      = [];
let runInProgress = false;

// ── Helpers ─────────────────────────────────────────────────
function showEl(el)  { el && el.removeAttribute('hidden'); }
function hideEl(el)  { el && el.setAttribute('hidden', ''); }

function setStatus(msg, variant = 'running') {
  showEl(runStatusEl);
  runStatusEl.className = `run-status run-status--${variant}`;
  runStatusEl.textContent = msg;
}

function clearStatus() { hideEl(runStatusEl); }

function statusBadge(status) {
  const map = { pass: 'pass', fail: 'fail', skip: 'skip', error: 'error', na: 'na' };
  const cls = map[status?.toLowerCase()] ?? 'na';
  return `<span class="badge badge--${cls}">${escHtml(status ?? 'N/A')}</span>`;
}

function gateBadge(passed) {
  if (passed === null || passed === undefined)
    return `<span class="gate-badge gate-badge--na">—</span>`;
  return passed
    ? `<span class="gate-badge gate-badge--pass">✅ Pass</span>`
    : `<span class="gate-badge gate-badge--fail">❌ Fail</span>`;
}

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtVal(v) {
  if (v === null || v === undefined || v === '') return '<span style="color:#94a3b8">N/A</span>';
  const n = parseFloat(v);
  if (isNaN(n)) return escHtml(v);
  return (n * 100).toFixed(1) + '%';
}

function fmtTimestamp(ts) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString();
  } catch { return ts; }
}

function colorClass(v) {
  if (v === null || v === undefined) return 'metric-cat-card__value--na';
  const n = parseFloat(v);
  if (isNaN(n)) return '';
  if (n >= 0.8)  return 'metric-cat-card__value--good';
  if (n >= 0.5)  return 'metric-cat-card__value--warn';
  return 'metric-cat-card__value--bad';
}

async function apiFetch(path, opts = {}) {
  const resp = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try { const d = await resp.json(); msg = d.error || d.detail || msg; } catch {}
    throw new Error(msg);
  }
  return resp.json();
}

// ── Trigger evaluation run ───────────────────────────────────
triggerRunBtn.addEventListener('click', async () => {
  if (runInProgress) return;
  runInProgress = true;
  triggerRunBtn.disabled = true;
  clearStatus();
  setStatus('🔄 Evaluation running… this may take 15–60 seconds.', 'running');

  const body = {
    task_type:         taskTypeSelect.value || null,
    dataset_version:   datasetVersionInput.value.trim() || '1.0',
    deterministic_only: deterministicOnly.checked,
    max_cases:         maxCasesInput.value ? parseInt(maxCasesInput.value) : null,
  };

  try {
    const data = await apiFetch('/api/evaluation/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    if (!data.success) throw new Error(data.error || 'Unknown error');

    const summary = data;
    const gateStr = summary.quality_gate_passed === true
      ? '✅ All quality gates passed'
      : summary.quality_gate_passed === false
        ? '❌ One or more quality gates failed'
        : '— Gate status unknown';

    setStatus(
      `✅ Run complete — ${summary.cases_evaluated ?? '?'} cases evaluated. ` +
      `${summary.cases_passed ?? '?'} passed, ${summary.cases_failed ?? '?'} failed. ${gateStr}`,
      'success'
    );

    await loadRunsList();
    if (summary.run_id) {
      await loadRunDetail(summary.run_id);
    }
  } catch (err) {
    setStatus(`❌ Evaluation failed: ${err.message}`, 'error');
  } finally {
    runInProgress = false;
    triggerRunBtn.disabled = false;
  }
});

// ── Load runs list ───────────────────────────────────────────
async function loadRunsList() {
  showEl(runsLoadingEl);
  hideEl(runsEmptyEl);
  hideEl(runsErrorEl);
  hideEl(runsTableEl);

  try {
    const data = await apiFetch('/api/evaluation/runs');
    hideEl(runsLoadingEl);

    if (!data.runs || data.runs.length === 0) {
      showEl(runsEmptyEl);
      return;
    }

    renderRunsTable(data.runs);
    showEl(runsTableEl);
  } catch (err) {
    hideEl(runsLoadingEl);
    showEl(runsErrorEl);
    runsErrorEl.textContent = `Failed to load runs: ${err.message}`;
  }
}

function renderRunsTable(runs) {
  runsTableBody.innerHTML = runs.map(r => {
    const gPassed = r.quality_gate_passed;
    const isSelected = r.run_id === currentRunId;
    return `
      <tr${isSelected ? ' style="background:#eef2ff"' : ''}>
        <td><code>${escHtml(r.run_id)}</code></td>
        <td>${fmtTimestamp(r.timestamp)}</td>
        <td>${escHtml(r.dataset_version ?? '—')}</td>
        <td>${r.cases_evaluated ?? '—'}</td>
        <td>${r.cases_passed ?? '—'}</td>
        <td>${r.cases_failed ?? '—'}</td>
        <td>${gateBadge(gPassed)}</td>
        <td>
          <button class="btn-view-run" data-run-id="${escHtml(r.run_id)}">
            View →
          </button>
        </td>
      </tr>`;
  }).join('');

  runsTableBody.querySelectorAll('.btn-view-run').forEach(btn => {
    btn.addEventListener('click', () => loadRunDetail(btn.dataset.runId));
  });
}

// ── Load run detail ──────────────────────────────────────────
async function loadRunDetail(runId) {
  currentRunId = runId;
  showEl(runDetailEl);

  // Reset sub-sections
  qualityGateBanner.className  = 'gate-banner';
  qualityGateBanner.innerHTML  = '';
  metricCategoryCards.innerHTML = '';
  hideEl(metricsTableWrap);
  hideEl(casesTableWrap);
  showEl(metricsLoadingEl);
  showEl(casesLoadingEl);
  hideEl(metricsErrorEl);
  hideEl(casesErrorEl);
  runMetadataPre.textContent = '';

  // Scroll to run detail
  runDetailEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Highlight selected row
  runsTableBody.querySelectorAll('tr').forEach(tr => {
    tr.style.background = '';
  });
  runsTableBody.querySelectorAll('.btn-view-run').forEach(btn => {
    if (btn.dataset.runId === runId) {
      btn.closest('tr').style.background = '#eef2ff';
    }
  });

  // Load metadata, metrics and cases in parallel
  const [metaResult, metricsResult, casesResult] = await Promise.allSettled([
    apiFetch(`/api/evaluation/runs/${encodeURIComponent(runId)}`),
    apiFetch(`/api/evaluation/runs/${encodeURIComponent(runId)}/metrics`),
    apiFetch(`/api/evaluation/runs/${encodeURIComponent(runId)}/cases`),
  ]);

  // ── Metadata / Gate banner ──
  if (metaResult.status === 'fulfilled' && metaResult.value.success) {
    const meta = metaResult.value;
    renderQualityGateBanner(meta);
    runMetadataPre.textContent = JSON.stringify(meta, null, 2);
  } else {
    qualityGateBanner.className = 'gate-banner gate-banner--na';
    qualityGateBanner.innerHTML = `
      <span class="gate-banner__icon">⚠️</span>
      <span class="gate-banner__msg">Could not load run metadata: ${
        metaResult.reason?.message ?? 'unknown error'
      }</span>`;
  }

  // ── Metrics ──
  hideEl(metricsLoadingEl);
  if (metricsResult.status === 'fulfilled' && metricsResult.value.success) {
    const metrics = metricsResult.value.metrics ?? {};
    renderMetricCategoryCards(metrics);
    renderMetricsTable(metrics);
    showEl(metricsTableWrap);
  } else {
    showEl(metricsErrorEl);
    metricsErrorEl.textContent = `Could not load metrics: ${
      metricsResult.reason?.message ?? 'unknown error'
    }`;
  }

  // ── Cases ──
  hideEl(casesLoadingEl);
  if (casesResult.status === 'fulfilled' && casesResult.value.success) {
    allCases = casesResult.value.cases ?? [];
    renderCasesTable(allCases);
    showEl(casesTableWrap);
  } else {
    showEl(casesErrorEl);
    casesErrorEl.textContent = `Could not load case results: ${
      casesResult.reason?.message ?? 'unknown error'
    }`;
  }
}

// ── Quality Gate Banner ──────────────────────────────────────
function renderQualityGateBanner(meta) {
  const passed = meta.quality_gate_passed;
  let cls, icon, msg;

  if (passed === true) {
    cls  = 'gate-banner--pass';
    icon = '✅';
    msg  = `All quality gates passed — Run <strong>${escHtml(meta.run_id)}</strong> ` +
           `(${meta.cases_evaluated ?? '?'} cases, ${fmtTimestamp(meta.timestamp)})`;
  } else if (passed === false) {
    const failed = meta.failed_gates ?? [];
    cls  = 'gate-banner--fail';
    icon = '❌';
    msg  = `Quality gate FAILED — Run <strong>${escHtml(meta.run_id)}</strong>. ` +
           (failed.length
             ? `Failing gates: <strong>${failed.map(escHtml).join(', ')}</strong>.`
             : 'See metrics for details.');
  } else {
    cls  = 'gate-banner--na';
    icon = 'ℹ️';
    msg  = `Run <strong>${escHtml(meta.run_id)}</strong> — Gate status unavailable.`;
  }

  qualityGateBanner.className = `gate-banner ${cls}`;
  qualityGateBanner.innerHTML = `
    <span class="gate-banner__icon">${icon}</span>
    <span class="gate-banner__msg">${msg}</span>`;
}

// ── Metric Category Cards ────────────────────────────────────
const CATEGORY_ORDER = [
  ['retrieval',        '🔍', 'Retrieval'],
  ['rag',              '🧠', 'RAG / Answers'],
  ['citation',         '🔗', 'Citations'],
  ['quiz',             '📝', 'Quiz Quality'],
  ['personalization',  '🎯', 'Personalization'],
  ['study_plan',       '📅', 'Study Planner'],
];

function renderMetricCategoryCards(metrics) {
  // Group metrics by category
  const grouped = {};
  Object.entries(metrics).forEach(([key, m]) => {
    const cat = m.category ?? 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push({ key, ...m });
  });

  // Build cards for each known category
  const cards = CATEGORY_ORDER.map(([catKey, icon, label]) => {
    const items = grouped[catKey] ?? [];
    if (items.length === 0) {
      return `<div class="metric-cat-card">
        <div class="metric-cat-card__label">${icon} ${escHtml(label)}</div>
        <div class="metric-cat-card__value metric-cat-card__value--na">N/A</div>
        <div class="metric-cat-card__sub">No cases evaluated</div>
      </div>`;
    }

    // Compute a representative value: mean of non-null values
    const vals = items.map(i => i.value).filter(v => v !== null && v !== undefined && !isNaN(parseFloat(v)));
    const avg  = vals.length ? vals.reduce((a, b) => a + parseFloat(b), 0) / vals.length : null;
    const cc   = avg !== null ? colorClass(avg) : 'metric-cat-card__value--na';
    const shown = avg !== null ? (avg * 100).toFixed(1) + '%' : 'N/A';
    const sub   = `${items.length} metric${items.length !== 1 ? 's' : ''}, ${
      items.reduce((s, i) => s + (i.n_cases ?? 0), 0)
    } cases`;

    return `<div class="metric-cat-card">
      <div class="metric-cat-card__label">${icon} ${escHtml(label)}</div>
      <div class="metric-cat-card__value ${cc}">${shown}</div>
      <div class="metric-cat-card__sub">${sub}</div>
    </div>`;
  }).join('');

  metricCategoryCards.innerHTML = cards;
}

// ── Full Metrics Table ───────────────────────────────────────
function renderMetricsTable(metrics) {
  const entries = Object.entries(metrics);
  if (entries.length === 0) {
    metricsTableBody.innerHTML = '<tr><td colspan="7" style="color:#94a3b8;text-align:center">No metrics recorded.</td></tr>';
    return;
  }

  let totalCases = 0;
  metricsTableBody.innerHTML = entries.map(([key, m]) => {
    const n = m.n_cases ?? 0;
    totalCases += n;
    const preliminary = n > 0 && n <= 5 ? ' <span title="Preliminary — ≤5 cases" style="color:#d97706;font-size:0.75rem">⚠️</span>' : '';
    const valStr = (m.value !== null && m.value !== undefined && !isNaN(parseFloat(m.value)))
      ? `<strong>${(parseFloat(m.value) * 100).toFixed(1)}%</strong>`
      : '<span style="color:#94a3b8">N/A</span>';

    return `<tr>
      <td><code>${escHtml(key)}</code></td>
      <td>${escHtml(m.category ?? '—')}</td>
      <td>${valStr}${preliminary}</td>
      <td>${n}</td>
      <td>${m.n_failed ?? 0} / ${m.n_unavailable ?? 0}</td>
      <td>${m.gate_required ? gateBadge(m.gate_passed) : '<span style="color:#94a3b8">—</span>'}</td>
      <td style="font-size:0.8rem;color:#475569;max-width:260px">${escHtml(m.definition ?? m.description ?? '')}</td>
    </tr>`;
  }).join('');

  metricSampleNote.textContent = `${entries.length} metrics · ${totalCases} total case evaluations`;
}

// ── Case Results Table ───────────────────────────────────────
function renderCasesTable(cases) {
  const statusF = caseFilterStatus.value;
  const typeF   = caseFilterType.value;

  const filtered = cases.filter(c => {
    if (statusF && (c.status ?? '').toLowerCase() !== statusF) return false;
    if (typeF   && (c.task_type ?? '').toLowerCase() !== typeF)   return false;
    return true;
  });

  if (filtered.length === 0) {
    casesTableBody.innerHTML = '<tr><td colspan="5" style="color:#94a3b8;text-align:center">No cases match the current filter.</td></tr>';
    casesCountEl.textContent = `0 of ${cases.length} cases shown.`;
    return;
  }

  casesTableBody.innerHTML = filtered.map(c => {
    const scoreStr = (c.score !== null && c.score !== undefined && !isNaN(parseFloat(c.score)))
      ? (parseFloat(c.score) * 100).toFixed(1) + '%'
      : '—';

    return `<tr>
      <td><code style="font-size:0.78rem">${escHtml(c.case_id ?? c.id ?? '—')}</code></td>
      <td>${escHtml(c.task_type ?? '—')}</td>
      <td>${statusBadge(c.status)}</td>
      <td>${scoreStr}</td>
      <td style="max-width:360px;word-break:break-word">${escHtml(c.message ?? c.error ?? '')}</td>
    </tr>`;
  }).join('');

  casesCountEl.textContent = `Showing ${filtered.length} of ${cases.length} cases.`;
}

// Re-render on filter change
caseFilterStatus.addEventListener('change', () => renderCasesTable(allCases));
caseFilterType.addEventListener('change',   () => renderCasesTable(allCases));

// ── Refresh button ───────────────────────────────────────────
refreshRunsBtn.addEventListener('click', loadRunsList);

// ── Auto-load most recent run detail ────────────────────────
async function maybeLoadLatestRun(runs) {
  if (runs && runs.length > 0) {
    await loadRunDetail(runs[0].run_id);
  }
}

// ── Init ─────────────────────────────────────────────────────
(async () => {
  await loadRunsList();
  // If runs exist, auto-show the most recent one
  try {
    const data = await apiFetch('/api/evaluation/runs');
    if (data.runs && data.runs.length > 0) {
      await maybeLoadLatestRun(data.runs);
    }
  } catch { /* silently skip */ }
})();
