/**
 * VIDYA-X AI — Learning Progress Page JavaScript (Step 8)
 * File: frontend/js/progress.js
 *
 * Responsibilities:
 *  1. Read vidyaXProfile from localStorage (student_id + course_id)
 *  2. Fetch learner mastery from backend
 *  3. Render overall mastery, topic bars, concept drill-down
 *  4. Render weak/strong topic sections
 *  5. Render recent activity from mastery timestamps
 *  6. Handle diagnostic quiz creation for new students
 *  7. Handle learner state reset
 *
 * IMPORTANT:
 *  - Does NOT store mastery in localStorage.
 *  - Backend database is the single source of truth.
 *  - Does NOT display fake values when backend is unavailable.
 *  - Does NOT treat no-history as 0% mastery.
 */

"use strict";

const API_BASE = "http://localhost:8000/api";

// ── State ────────────────────────────────────────────────────────────────────
let studentId  = null;
let courseId   = null;
let allTopics  = [];
let allConcepts = [];

// ── DOM references ────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const progressLoading  = $("progressLoading");
const progressError    = $("progressError");
const progressNoData   = $("progressNoData");
const progressContent  = $("progressContent");
const progressErrorMsg = $("progressErrorMsg");
const progressSubtitle = $("progressSubtitle");

const overallPct      = $("overallPct");
const overallCircle   = $("overallCircle");
const statPills       = $("statPills");

const diagnosticCta   = $("diagnosticCta");
const startDiagnosticBtn = $("startDiagnosticBtn");

const topicList       = $("topicList");
const conceptsSection = $("conceptsSection");
const conceptsSectionTitle = $("conceptsSectionTitle");
const conceptList     = $("conceptList");
const closeConceptsBtn = $("closeConceptsBtn");

const weakList        = $("weakList");
const strongList      = $("strongList");
const activityList    = $("activityList");

const resetBtn        = $("resetBtn");
const resetConfirm    = $("resetConfirm");
const confirmResetBtn = $("confirmResetBtn");
const cancelResetBtn  = $("cancelResetBtn");

// ── Init ─────────────────────────────────────────────────────────────────────

(async function init() {
  // 1. Read profile from localStorage
  try {
    const profile = JSON.parse(localStorage.getItem("vidyaXProfile") || "{}");
    studentId = profile.studentId || profile.student_id || null;
    courseId  = profile.courseId  || profile.course_id  || null;

    // Try to infer courseId from uploaded materials
    if (!courseId) {
      const mats = JSON.parse(localStorage.getItem("vidyaXMaterials") || "[]");
      if (mats.length > 0 && mats[0].courseId) {
        courseId = mats[0].courseId;
      }
    }
  } catch (_) {}

  if (!studentId || !courseId) {
    showError(
      "Could not find your student or course profile.<br>" +
      "Please complete your profile on the home page first."
    );
    return;
  }

  progressSubtitle.textContent = `Student: ${studentId} | Course: ${courseId}`;

  // 2. Fetch all mastery data in parallel
  try {
    const [masteryResp, weakResp, strongResp, conceptsResp] = await Promise.all([
      apiFetch(`/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/mastery`),
      apiFetch(`/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/weak-topics`),
      apiFetch(`/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/strong-topics`),
      apiFetch(`/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/concepts`),
    ]);

    hideLoading();

    const hasHistory = masteryResp.has_history;
    allTopics   = masteryResp.topics   || [];
    allConcepts = conceptsResp.concepts || [];

    if (!hasHistory) {
      showNoData();
      return;
    }

    // 3. Render everything
    showContent();
    renderOverall(masteryResp);
    renderTopics(allTopics);
    renderWeak(weakResp.weak_topics   || []);
    renderStrong(strongResp.strong_topics || []);
    renderActivity(allTopics, allConcepts);

  } catch (err) {
    hideLoading();
    showError(
      "Learning progress is temporarily unavailable.<br>" +
      "Please make sure the backend is running on port 8000."
    );
  }
})();

// ── Fetch helper ─────────────────────────────────────────────────────────────

async function apiFetch(path) {
  const resp = await fetch(API_BASE + path);
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── State toggles ─────────────────────────────────────────────────────────────

function hideLoading()   { progressLoading.hidden = true; }
function showError(msg)  {
  progressLoading.hidden = true;
  progressErrorMsg.innerHTML = msg;
  progressError.hidden = false;
}
function showNoData()    { progressNoData.hidden = false; diagnosticCta.hidden = false; }
function showContent()   { progressContent.hidden = false; }

// ── Overall mastery ───────────────────────────────────────────────────────────

function renderOverall(data) {
  const overall = data.overall_mastery;
  const topics  = data.topics || [];

  if (overall === null || overall === undefined) {
    overallPct.textContent = "--";
  } else {
    overallPct.textContent = `${Math.round(overall * 100)}%`;
    // Colour circle by mastery
    if (overall >= 0.80)      overallCircle.style.background = "#38a169";
    else if (overall >= 0.50) overallCircle.style.background = "#d69e2e";
    else                      overallCircle.style.background = "#e53e3e";
  }

  // Stat pills
  const mastered   = topics.filter(t => t.state === "Mastered").length;
  const developing = topics.filter(t => t.state === "Developing").length;
  const needsReview = topics.filter(t => t.state === "Needs Review").length;

  statPills.innerHTML = "";
  if (mastered)    statPills.appendChild(pill(`${mastered} Mastered`, "pill-mastered"));
  if (developing)  statPills.appendChild(pill(`${developing} Developing`, "pill-developing"));
  if (needsReview) statPills.appendChild(pill(`${needsReview} Needs Review`, "pill-weak"));
}

function pill(text, cls) {
  const span = document.createElement("span");
  span.className = `stat-pill ${cls}`;
  span.textContent = text;
  return span;
}

// ── Topic list ────────────────────────────────────────────────────────────────

function renderTopics(topics) {
  topicList.innerHTML = "";
  if (topics.length === 0) {
    topicList.innerHTML = '<p class="empty-hint">No topics assessed yet.</p>';
    return;
  }

  // Sort: Needs Review first, then Developing, then Mastered
  const order = { "Needs Review": 0, "Developing": 1, "Mastered": 2 };
  const sorted = [...topics].sort((a, b) =>
    (order[a.state] ?? 3) - (order[b.state] ?? 3)
  );

  sorted.forEach(topic => {
    const pct = Math.round((topic.mastery || 0) * 100);
    const barClass = stateBarClass(topic.state);
    const badgeClass = stateBadgeClass(topic.state);

    const card = document.createElement("div");
    card.className = "topic-card";
    card.dataset.topicId = topic.topic_id;
    card.innerHTML = `
      <div class="topic-card-header">
        <span class="topic-name">${escHtml(topic.topic_name)}</span>
        <span class="topic-state-badge ${badgeClass}">${escHtml(topic.state)}</span>
      </div>
      <div class="topic-pct-text">${pct}%</div>
      <div class="topic-bar-wrap">
        <div class="topic-bar-fill ${barClass}" style="width: ${pct}%"></div>
      </div>
      <div class="topic-stats">
        <span>Attempts: ${topic.attempt_count}</span>
        <span>Correct: ${topic.correct_count}</span>
        <span>Incorrect: ${topic.incorrect_count}</span>
      </div>
      <p class="drill-hint">Click to view concept breakdown</p>
    `;
    card.addEventListener("click", () => showConceptsForTopic(topic));
    topicList.appendChild(card);
  });
}

// ── Concept drill-down ────────────────────────────────────────────────────────

function showConceptsForTopic(topic) {
  const topicConcepts = allConcepts.filter(c => c.topic_id === topic.topic_id);

  conceptsSectionTitle.textContent = `\uD83E\uDDE0 Concepts — ${topic.topic_name}`;
  conceptList.innerHTML = "";

  if (topicConcepts.length === 0) {
    conceptList.innerHTML = '<p class="empty-hint">No concept data for this topic yet.</p>';
  } else {
    topicConcepts.forEach(c => {
      const pct = Math.round((c.mastery || 0) * 100);
      const barClass = stateBarClass(c.state);
      const row = document.createElement("div");
      row.className = "concept-row";
      row.innerHTML = `
        <span class="concept-name">${escHtml(c.concept_name)}</span>
        <div class="concept-bar-wrap">
          <div class="concept-bar-fill ${barClass}" style="width: ${pct}%"></div>
        </div>
        <span class="concept-pct">${pct}%</span>
        <span class="concept-state ${badgeClass(c.state)}">${escHtml(c.state)}</span>
      `;
      conceptList.appendChild(row);
    });
  }

  conceptsSection.hidden = false;
  conceptsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

closeConceptsBtn.addEventListener("click", () => {
  conceptsSection.hidden = true;
});

function badgeClass(state) {
  if (state === "Mastered")     return "badge-mastered";
  if (state === "Developing")   return "badge-developing";
  return "badge-needs-review";
}

// ── Weak topics ───────────────────────────────────────────────────────────────

function renderWeak(weakTopics) {
  weakList.innerHTML = "";
  if (weakTopics.length === 0) {
    weakList.innerHTML = '<p class="empty-hint">No topics below the review threshold. Keep it up!</p>';
    return;
  }
  weakTopics.forEach(t => {
    const pct = Math.round((t.mastery || 0) * 100);
    const item = document.createElement("div");
    item.className = "weak-item";
    item.innerHTML = `
      <span class="weak-item-name">${escHtml(t.topic_name)}</span>
      <span class="weak-item-pct">${pct}%</span>
      <span class="weak-reason">${escHtml(t.reason || "Low estimated mastery based on recent assessment performance")}</span>
    `;
    weakList.appendChild(item);
  });
}

// ── Strong topics ─────────────────────────────────────────────────────────────

function renderStrong(strongTopics) {
  strongList.innerHTML = "";
  if (strongTopics.length === 0) {
    strongList.innerHTML = '<p class="empty-hint">No mastered topics yet — keep practicing!</p>';
    return;
  }
  strongTopics.forEach(t => {
    const pct = Math.round((t.mastery || 0) * 100);
    const item = document.createElement("div");
    item.className = "strong-item";
    item.innerHTML = `
      <span class="strong-item-name">${escHtml(t.topic_name)}</span>
      <span class="strong-item-pct">${pct}% — Mastered</span>
    `;
    strongList.appendChild(item);
  });
}

// ── Recent activity ───────────────────────────────────────────────────────────

function renderActivity(topics, concepts) {
  // Build activity from recent topic/concept mastery timestamps
  const events = [];

  topics.forEach(t => {
    if (t.last_correct_at) {
      events.push({
        ts:    new Date(t.last_correct_at),
        name:  t.topic_name,
        result: "correct",
        mastery: t.mastery,
      });
    }
    if (t.last_incorrect_at) {
      events.push({
        ts:    new Date(t.last_incorrect_at),
        name:  t.topic_name,
        result: "incorrect",
        mastery: t.mastery,
      });
    }
  });

  // Sort newest first
  events.sort((a, b) => b.ts - a.ts);

  activityList.innerHTML = "";
  const recent = events.slice(0, 10);

  if (recent.length === 0) {
    activityList.innerHTML = '<p class="empty-hint">No recent activity recorded.</p>';
    return;
  }

  recent.forEach(ev => {
    const icon = ev.result === "correct" ? "&#x2705;" : "&#x274C;";
    const resultClass = ev.result === "correct" ? "result-correct" : "result-incorrect";
    const resultText  = ev.result === "correct" ? "Correct" : "Incorrect";

    const item = document.createElement("div");
    item.className = "activity-item";
    item.innerHTML = `
      <span class="activity-icon">${icon}</span>
      <div class="activity-body">
        <div class="activity-name">${escHtml(ev.name)}</div>
        <div class="activity-result ${resultClass}">${resultText}</div>
        <div class="activity-mastery-change">
          Estimated mastery: ${Math.round((ev.mastery || 0) * 100)}%
        </div>
      </div>
      <span class="activity-time">${formatRelativeTime(ev.ts)}</span>
    `;
    activityList.appendChild(item);
  });
}

// ── Diagnostic ────────────────────────────────────────────────────────────────

startDiagnosticBtn.addEventListener("click", async () => {
  startDiagnosticBtn.disabled = true;
  startDiagnosticBtn.textContent = "Creating diagnostic…";

  try {
    const resp = await fetch(
      `${API_BASE}/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/diagnostic`,
      { method: "POST" }
    );
    const data = await resp.json();

    if (data.quiz_id) {
      // Redirect to quiz page
      window.location.href = `quiz.html?quiz_id=${encodeURIComponent(data.quiz_id)}`;
    } else {
      alert(data.message || data.error || "Could not create diagnostic.");
    }
  } catch (_) {
    startDiagnosticBtn.disabled = false;
    startDiagnosticBtn.textContent = "Start Diagnostic";
  }
});

// ── Reset ─────────────────────────────────────────────────────────────────────

resetBtn.addEventListener("click", () => {
  resetConfirm.hidden = false;
});

cancelResetBtn.addEventListener("click", () => {
  resetConfirm.hidden = true;
});

confirmResetBtn.addEventListener("click", async () => {
  confirmResetBtn.disabled = true;
  try {
    const resp = await fetch(
      `${API_BASE}/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/reset`,
      { method: "DELETE" }
    );
    const data = await resp.json();
    if (data.success) {
      // Reload to reflect cleared state
      window.location.reload();
    } else {
      confirmResetBtn.disabled = false;
      resetConfirm.hidden = true;
    }
  } catch (_) {
    confirmResetBtn.disabled = false;
    resetConfirm.hidden = true;
  }
});

// ── Utilities ─────────────────────────────────────────────────────────────────

function stateBarClass(state) {
  if (state === "Mastered")   return "bar-mastered";
  if (state === "Developing") return "bar-developing";
  return "bar-needs-review";
}

function stateBadgeClass(state) {
  if (state === "Mastered")   return "badge-mastered";
  if (state === "Developing") return "badge-developing";
  return "badge-needs-review";
}

function escHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatRelativeTime(date) {
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1)   return "Just now";
  if (diffMin < 60)  return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24)   return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7)  return `${diffDays} days ago`;
  return date.toLocaleDateString();
}
