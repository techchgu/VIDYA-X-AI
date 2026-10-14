/**
 * VIDYA-X AI — Adaptive Quiz Engine JavaScript (Step 7 & Step 9)
 * File: frontend/js/quiz.js
 *
 * Handles:
 *  - Read student profile from localStorage (vidyaXProfile)
 *  - Setup form & Mode selection (Standard vs AI Adaptive Practice)
 *  - Real-time adaptive loop: BKT mastery updates & dynamic next question selection
 *  - Answers submission: POST /api/quiz/{quiz_id}/answer
 *  - BKT Mastery feedback display ("estimated mastery increased from X% to Y%")
 *  - Adaptive session summary at completion
 */

"use strict";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const API_BASE = "http://localhost:8000/api";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let state = {
  quizId: null,
  questions: [],           // raw question objects
  currentIndex: 0,
  mode: "practice",        // practice | exam
  isAdaptive: true,        // Step 9 adaptive flag
  courseId: null,
  studentId: "student_demo",
  answeredIds: new Set(),  // question ids already submitted
  masteryChanges: [],      // tracks BKT updates for final summary
};

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

const panels = {
  setup:    $("setupPanel"),
  loading:  $("loadingPanel"),
  quiz:     $("quizPanel"),
  results:  $("resultsPanel"),
};

// Setup
const courseInput       = $("courseIdInput");
const topicInput        = $("topicInput");
const countInput        = $("countInput");
const diffSelect        = $("difficultySelect");
const modeSelect        = $("modeSelect");
const generateBtn       = $("generateBtn");
const setupError        = $("setupError");

// Quiz panel
const quizTitle         = $("quizTitle");
const questionCounter   = $("questionCounter");
const diffBadge         = $("diffBadge");
const progressFill      = $("progressFill");
const questionPrompt    = $("questionPrompt");
const optionsGrid       = $("optionsGrid");
const textAnswerWrap    = $("textAnswerWrap");
const textAnswer        = $("textAnswer");
const sourceRefs        = $("sourceRefs");
const sourceList        = $("sourceList");
const feedbackBox       = $("feedbackBox");
const feedbackResult    = $("feedbackResult");
const feedbackText      = $("feedbackText");
const explanationText   = $("explanationText");
const masteryChangeCallout = $("masteryChangeCallout");
const adaptiveBanner    = $("adaptiveBanner");
const adaptiveReasonText = $("adaptiveReasonText");
const submitAnswerBtn   = $("submitAnswerBtn");
const nextBtn           = $("nextBtn");
const skipBtn           = $("skipBtn");

// Results
const scorePct          = $("scorePct");
const scoreGrade        = $("scoreGrade");
const correctCount      = $("correctCount");
const totalCount        = $("totalCount");
const scoreMessage      = $("scoreMessage");
const resultsBreakdown  = $("resultsBreakdown");
const adaptiveSummaryCard = $("adaptiveSummaryCard");
const masteryChangesList  = $("masteryChangesList");
const retryBtn          = $("retryBtn");

// ---------------------------------------------------------------------------
// Panel switcher
// ---------------------------------------------------------------------------
function showPanel(name) {
  Object.entries(panels).forEach(([key, el]) => {
    el.hidden = key !== name;
  });
}

// ---------------------------------------------------------------------------
// Error display helpers
// ---------------------------------------------------------------------------
function showSetupError(msg) {
  setupError.textContent = msg;
  setupError.hidden = false;
}

function clearSetupError() {
  setupError.textContent = "";
  setupError.hidden = true;
}

// ---------------------------------------------------------------------------
// Pre-fill course ID & mode from URL or localStorage
// ---------------------------------------------------------------------------
(function init() {
  try {
    const profile = JSON.parse(localStorage.getItem("vidyaXProfile") || "{}");
    if (profile.studentId) {
      state.studentId = profile.studentId;
    }
    const materials = JSON.parse(localStorage.getItem("vidyaXMaterials") || "[]");
    if (materials.length > 0 && materials[0].courseId) {
      courseInput.value = materials[0].courseId;
    }

    // Check URL parameters (e.g. quiz.html?mode=adaptive&course_id=physics-101)
    const urlParams = new URLSearchParams(window.location.search);
    const modeParam = urlParams.get("mode");
    const courseParam = urlParams.get("course_id");

    if (courseParam) {
      courseInput.value = courseParam;
    }

    if (modeParam === "adaptive") {
      const adaptiveRadio = document.querySelector("input[name='practiceMode'][value='adaptive']");
      if (adaptiveRadio) adaptiveRadio.checked = true;
    }
  } catch (_) {
    // ignore localStorage errors
  }
})();

// ---------------------------------------------------------------------------
// Generate / Start Quiz
// ---------------------------------------------------------------------------
generateBtn.addEventListener("click", async () => {
  clearSetupError();

  const courseId   = courseInput.value.trim();
  const topic      = topicInput.value.trim() || "General";
  const count      = parseInt(countInput.value, 10) || 5;
  const difficulty = diffSelect.value;
  const mode       = modeSelect.value;

  const selectedModeRadio = document.querySelector("input[name='practiceMode']:checked");
  const isAdaptive = selectedModeRadio ? selectedModeRadio.value === "adaptive" : true;

  const selectedTypes = Array.from(
    document.querySelectorAll("input[name='qtype']:checked")
  ).map((cb) => cb.value);

  // Validation
  if (!courseId) { showSetupError("Please enter a Course ID."); courseInput.focus(); return; }
  if (selectedTypes.length === 0) { showSetupError("Select at least one question type."); return; }
  if (count < 1 || count > 20)    { showSetupError("Number of questions must be between 1 and 20."); return; }

  state.mode = mode;
  state.isAdaptive = isAdaptive;
  state.courseId = courseId;
  state.masteryChanges = [];

  showPanel("loading");

  try {
    let endpoint = `${API_BASE}/quiz/generate`;
    let bodyData = {
      course_id:      courseId,
      topic_query:    topic,
      question_types: selectedTypes,
      count,
      difficulty,
      mode,
      student_id: state.studentId || "student_demo",
      title: isAdaptive ? `AI Adaptive Practice — ${courseId}` : `${topic} Quiz`,
      adaptive: isAdaptive,
    };

    if (isAdaptive) {
      endpoint = `${API_BASE}/adaptive/quiz`;
      bodyData = {
        student_id: state.studentId || "student_demo",
        course_id: courseId,
        count: count,
        question_types: selectedTypes,
      };
    }

    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyData),
    });

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      showPanel("setup");
      if (data.status === "cold_start") {
        showSetupError("Cold Start: Complete a diagnostic or answer a few questions first to enable personalized practice.");
      } else {
        showSetupError(data.error || "Failed to generate quiz. Ensure course materials have been ingested.");
      }
      return;
    }

    // Store quiz state
    state.quizId     = data.quiz_id;
    state.questions  = data.questions || [];
    state.currentIndex = 0;
    state.answeredIds = new Set();

    if (state.questions.length === 0) {
      showPanel("setup");
      showSetupError("No questions available. Upload and ingest course materials first.");
      return;
    }

    quizTitle.textContent = isAdaptive ? `⚡ AI Adaptive Practice (${courseId})` : (data.title || "Practice Quiz");
    showPanel("quiz");
    renderQuestion();

  } catch (err) {
    showPanel("setup");
    showSetupError("Could not connect to the backend. Make sure it is running on port 8000.");
  }
});

// ---------------------------------------------------------------------------
// Render current question
// ---------------------------------------------------------------------------
function renderQuestion() {
  const q = state.questions[state.currentIndex];
  const total = state.questions.length;
  const idx   = state.currentIndex;

  // Counter & progress
  questionCounter.textContent = `Question ${idx + 1} of ${total}`;
  progressFill.style.width = `${((idx) / total) * 100}%`;

  // Difficulty badge
  diffBadge.textContent  = q.difficulty || "medium";
  diffBadge.className    = `difficulty-badge ${q.difficulty || "medium"}`;

  // Adaptive Reason Banner
  if (state.isAdaptive && (q.selection_reason || q.reason)) {
    adaptiveReasonText.textContent = q.selection_reason || q.reason;
    adaptiveBanner.hidden = false;
  } else {
    adaptiveBanner.hidden = true;
  }

  // Prompt
  questionPrompt.textContent = q.prompt;

  // Clear previous feedback / sources / mastery callouts
  hideFeedback();
  clearSources();

  // Source refs
  renderSources(q.source_refs || []);

  // Reset nav buttons
  submitAnswerBtn.hidden = false;
  submitAnswerBtn.disabled = false;
  nextBtn.hidden = true;
  skipBtn.hidden = false;

  // Render answer input
  if (q.question_type === "mcq") {
    renderMcqOptions(q.options || []);
    optionsGrid.hidden    = false;
    textAnswerWrap.hidden = true;
  } else {
    optionsGrid.hidden    = true;
    textAnswerWrap.hidden = false;
    textAnswer.value      = "";
    textAnswer.placeholder =
      q.question_type === "numerical"
        ? "Enter a numerical value…"
        : "Type your answer here…";
  }
}

// ---------------------------------------------------------------------------
// MCQ option buttons
// ---------------------------------------------------------------------------
function renderMcqOptions(options) {
  optionsGrid.innerHTML = "";
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.dataset.key = opt.key;
    btn.innerHTML = `<span class="option-key">${opt.key}.</span>${escHtml(opt.text)}`;
    btn.addEventListener("click", () => selectOption(btn));
    optionsGrid.appendChild(btn);
  });
}

function selectOption(clickedBtn) {
  if (submitAnswerBtn.disabled) return;
  optionsGrid.querySelectorAll(".option-btn").forEach((b) => b.classList.remove("selected"));
  clickedBtn.classList.add("selected");
}

function getSelectedMcqKey() {
  const sel = optionsGrid.querySelector(".option-btn.selected");
  return sel ? sel.dataset.key : null;
}

// ---------------------------------------------------------------------------
// Submit answer & Real-Time BKT Update
// ---------------------------------------------------------------------------
submitAnswerBtn.addEventListener("click", async () => {
  const q = state.questions[state.currentIndex];
  let studentAnswer = "";

  if (q.question_type === "mcq") {
    studentAnswer = getSelectedMcqKey();
    if (!studentAnswer) {
      showFeedbackMessage("Select an option before submitting.", "partial");
      return;
    }
  } else {
    studentAnswer = textAnswer.value.trim();
    if (!studentAnswer) {
      showFeedbackMessage("Please type your answer before submitting.", "partial");
      return;
    }
  }

  submitAnswerBtn.disabled = true;
  skipBtn.hidden = true;

  try {
    const resp = await fetch(`${API_BASE}/quiz/${state.quizId}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_id:    q.id,
        student_answer: studentAnswer,
        student_id:     state.studentId || "student_demo",
      }),
    });

    const data = await resp.json();
    state.answeredIds.add(q.id);

    if (!resp.ok || !data.success) {
      showFeedbackMessage(data.error || "Submission failed.", "wrong");
      submitAnswerBtn.disabled = false;
      return;
    }

    // Process BKT Mastery Updates
    if (data.mastery_update) {
      const mu = data.mastery_update;
      const targetObj = mu.concept || mu.topic;
      if (targetObj) {
        const name = targetObj.name || "this topic";
        const priorPct = Math.round((targetObj.prior_mastery || 0.20) * 100);
        const newPct   = Math.round((targetObj.mastery || 0.20) * 100);
        const verb = data.is_correct ? "increased" : "changed";

        state.masteryChanges.push({
          name: name,
          prior: priorPct,
          current: newPct,
          isCorrect: data.is_correct,
        });

        masteryChangeCallout.innerHTML = `📊 <strong>Learner Model Update:</strong> Your estimated mastery of <em>${escHtml(name)}</em> ${verb} from <strong>${priorPct}%</strong> to <strong>${newPct}%</strong>.`;
        masteryChangeCallout.hidden = false;
      }
    }

    // Process Misconception Analysis Callout (Step 10)
    const callout = $("misconceptionCallout");
    if (callout) {
      if (data.misconception_analysis && data.misconception_analysis.detected && data.misconception_analysis.findings && data.misconception_analysis.findings.length > 0) {
        const finding = data.misconception_analysis.findings[0];
        const titleEl = $("misconceptionTitle");
        const descEl = $("misconceptionDesc");
        const evEl = $("misconceptionEvidence");
        const linkEl = $("remediationLink");

        if (titleEl) titleEl.textContent = `⚠️ Misconception Detected: ${finding.title || "Review Needed"}`;
        if (descEl) descEl.textContent = finding.description || "A recurring misunderstanding was detected from your response.";
        if (evEl) evEl.textContent = finding.evidence_summary ? `Evidence: "${finding.evidence_summary}"` : "";
        if (linkEl) linkEl.href = `remediation.html?misconception_id=${finding.id}&course_id=${encodeURIComponent(state.courseId)}`;

        callout.hidden = false;
      } else {
        callout.hidden = true;
      }
    }

    if (state.mode === "practice") {
      showAnswerFeedback(data, q);
    }

    if (q.question_type === "mcq") {
      highlightMcqAnswer(data.correct_answer, studentAnswer);
    }

    submitAnswerBtn.hidden = true;
    nextBtn.hidden = false;
    nextBtn.textContent =
      state.currentIndex < state.questions.length - 1
        ? "Next Question \u2192"
        : "See Results";

  } catch (_) {
    showFeedbackMessage("Network error. Could not submit answer.", "wrong");
    submitAnswerBtn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Skip
// ---------------------------------------------------------------------------
skipBtn.addEventListener("click", () => {
  submitAnswerBtn.hidden = true;
  nextBtn.hidden = false;
  skipBtn.hidden = true;
  nextBtn.textContent =
    state.currentIndex < state.questions.length - 1
      ? "Next Question \u2192"
      : "See Results";
});

// ---------------------------------------------------------------------------
// Next Question (Fetch Dynamic Adaptive Next Question in Adaptive Mode)
// ---------------------------------------------------------------------------
nextBtn.addEventListener("click", async () => {
  if (state.currentIndex < state.questions.length - 1) {
    state.currentIndex++;

    // True Real-Time Adaptation (Step 26): Dynamic next question fetch
    if (state.isAdaptive) {
      try {
        const adaptiveResp = await fetch(
          `${API_BASE}/adaptive/next-question?student_id=${encodeURIComponent(state.studentId || "student_demo")}&course_id=${encodeURIComponent(state.courseId)}&quiz_id=${encodeURIComponent(state.quizId)}`
        );
        const adaptiveData = await adaptiveResp.json();

        if (adaptiveResp.ok && adaptiveData.success && adaptiveData.question) {
          const nextQ = adaptiveData.question;
          nextQ.selection_reason = adaptiveData.reason;
          nextQ.estimated_mastery = adaptiveData.mastery;
          state.questions[state.currentIndex] = nextQ;
        }
      } catch (e) {
        console.warn("[ADAPTIVE] Could not dynamically fetch next question:", e);
      }
    }

    renderQuestion();
  } else {
    await showResults();
  }
});

// ---------------------------------------------------------------------------
// Feedback helpers
// ---------------------------------------------------------------------------
function showAnswerFeedback(data, q) {
  const correct = data.is_correct;
  const partial = !correct && (data.score || 0) > 0;

  let fbClass = correct ? "correct-fb" : (partial ? "partial-fb" : "wrong-fb");
  feedbackBox.className = `feedback-box ${fbClass}`;

  feedbackResult.textContent = correct
    ? "✓ Correct!"
    : (partial ? "Partially correct" : "✗ Incorrect");

  feedbackText.textContent = data.feedback || "";
  explanationText.textContent = data.explanation
    ? `Explanation: ${data.explanation}`
    : "";

  feedbackBox.hidden = false;
}

function showFeedbackMessage(msg, type) {
  feedbackBox.className = `feedback-box ${type === "wrong" ? "wrong-fb" : "partial-fb"}`;
  feedbackResult.textContent = "";
  feedbackText.textContent   = msg;
  explanationText.textContent = "";
  feedbackBox.hidden = false;
}

function hideFeedback() {
  feedbackBox.hidden = true;
  feedbackBox.className = "feedback-box";
  masteryChangeCallout.hidden = true;
  masteryChangeCallout.innerHTML = "";
  const callout = $("misconceptionCallout");
  if (callout) callout.hidden = true;
}

function highlightMcqAnswer(correctKey, studentKey) {
  optionsGrid.querySelectorAll(".option-btn").forEach((btn) => {
    btn.disabled = true;
    btn.classList.remove("selected");
    if (btn.dataset.key === correctKey) {
      btn.classList.add("correct");
    } else if (btn.dataset.key === studentKey && studentKey !== correctKey) {
      btn.classList.add("wrong");
    }
  });
}

// ---------------------------------------------------------------------------
// Source references
// ---------------------------------------------------------------------------
function renderSources(refs) {
  sourceList.innerHTML = "";
  const valid = refs.filter((r) => r && r.file_name);
  if (valid.length === 0) { sourceRefs.hidden = true; return; }

  valid.forEach((r) => {
    const li = document.createElement("li");
    let parts = [r.file_name];
    if (r.page)            parts.push(`Page ${r.page}`);
    if (r.slide)           parts.push(`Slide ${r.slide}`);
    if (r.timestamp_start) parts.push(`@ ${r.timestamp_start}`);
    li.textContent = parts.join(" — ");
    sourceList.appendChild(li);
  });
  sourceRefs.hidden = false;
}

function clearSources() {
  sourceList.innerHTML = "";
  sourceRefs.hidden = true;
}

// ---------------------------------------------------------------------------
// Results panel & Adaptive Summary
// ---------------------------------------------------------------------------
async function showResults() {
  showPanel("loading");

  try {
    const resp = await fetch(`${API_BASE}/quiz/${state.quizId}/result`);
    const data = await resp.json();

    if (!resp.ok || !data.success) {
      renderLocalResults();
      return;
    }

    // Score summary
    scorePct.textContent   = `${data.score_percent}%`;
    scoreGrade.textContent = `Grade: ${data.grade}`;
    correctCount.textContent = data.correct;
    totalCount.textContent   = data.total_questions;
    scoreMessage.textContent = getScoreMessage(data.score_percent);

    // Render Adaptive Session Summary (Step 32)
    if (state.isAdaptive && state.masteryChanges.length > 0) {
      masteryChangesList.innerHTML = "";
      state.masteryChanges.forEach((change) => {
        const item = document.createElement("div");
        item.style.padding = "0.4rem 0";
        item.style.borderBottom = "1px solid #e2e8f0";
        const icon = change.current >= change.prior ? "📈" : "📉";
        item.innerHTML = `${icon} <strong>${escHtml(change.name)}</strong>: ${change.prior}% → <strong>${change.current}%</strong>`;
        masteryChangesList.appendChild(item);
      });
      adaptiveSummaryCard.hidden = false;
    } else {
      adaptiveSummaryCard.hidden = true;
    }

    // Per-question breakdown
    resultsBreakdown.innerHTML = "";
    (data.questions || []).forEach((q, i) => {
      const item = document.createElement("div");
      const status = q.is_correct === null ? "skipped" : (q.is_correct ? "correct" : "wrong");
      item.className = `result-item item-${status}`;

      item.innerHTML = `
        <p class="result-prompt">${i + 1}. ${escHtml(q.prompt)}</p>
        <div class="result-answer-row">
          <span class="result-label">Your answer:</span>
          <span class="result-value">${escHtml(q.student_answer || "—")}</span>
          <span class="result-label">Correct:</span>
          <span class="result-value">${escHtml(q.correct_answer || "—")}</span>
        </div>
        ${q.explanation ? `<p class="result-explain">${escHtml(q.explanation)}</p>` : ""}
      `;
      resultsBreakdown.appendChild(item);
    });

    showPanel("results");

  } catch (_) {
    renderLocalResults();
  }
}

function renderLocalResults() {
  const total   = state.questions.length;
  const answered = state.answeredIds.size;
  scorePct.textContent   = "--";
  scoreGrade.textContent = "";
  correctCount.textContent = answered;
  totalCount.textContent   = total;
  scoreMessage.textContent = "Quiz complete.";
  resultsBreakdown.innerHTML = "";
  showPanel("results");
}

function getScoreMessage(pct) {
  if (pct >= 90) return "Outstanding! Keep up the excellent work!";
  if (pct >= 75) return "Great job! You have a strong grasp of the material.";
  if (pct >= 60) return "Good effort! Review the incorrect answers to improve.";
  if (pct >= 40) return "Keep practicing — revisit the source material for better results.";
  return "Don't give up! Review your course materials and try again.";
}

// ---------------------------------------------------------------------------
// Retry
// ---------------------------------------------------------------------------
retryBtn.addEventListener("click", () => {
  state = {
    quizId: null,
    questions: [],
    currentIndex: 0,
    mode: "practice",
    isAdaptive: true,
    courseId: state.courseId,
    studentId: state.studentId,
    answeredIds: new Set(),
    masteryChanges: [],
  };
  clearSetupError();
  showPanel("setup");
});

// ---------------------------------------------------------------------------
// Utility: HTML escaping
// ---------------------------------------------------------------------------
function escHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
