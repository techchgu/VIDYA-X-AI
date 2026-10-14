/**
 * VIDYA-X AI — Personalized Remediation Logic (Step 10)
 * File: frontend/js/remediation.js
 *
 * Responsibilities:
 *  - Reads studentId, courseId, misconceptionId, or sessionId from URL params / profile
 *  - Calls POST /api/remediation or GET /api/remediation/{session_id}
 *  - Renders corrective explanation, mistake vs correct comparison, worked example, source citations, self-check, practice
 *  - Tracks completion via POST /api/remediation/{session_id}/complete
 */

"use strict";

const API_BASE = "http://localhost:8000/api";

let state = {
  studentId: "student_demo",
  courseId: "general",
  sessionId: null,
  sessionData: null,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const profile = JSON.parse(localStorage.getItem("vidyaXProfile") || "{}");
    if (profile.studentId) state.studentId = profile.studentId;
    if (profile.courseId || profile.courseName) state.courseId = profile.courseId || profile.courseName;
  } catch (_) {}

  const urlParams = new URLSearchParams(window.location.search);
  const sessionParam = urlParams.get("session_id");
  const misconceptionParam = urlParams.get("misconception_id");
  const conceptParam = urlParams.get("concept_id");
  const topicParam = urlParams.get("topic_id");
  const courseParam = urlParams.get("course_id");

  if (courseParam) state.courseId = courseParam;

  if (sessionParam) {
    state.sessionId = sessionParam;
    await loadExistingSession(sessionParam);
  } else {
    await createNewSession(topicParam, conceptParam, misconceptionParam);
  }
});

async function createNewSession(topicId, conceptId, misconceptionId) {
  try {
    const resp = await fetch(`${API_BASE}/remediation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: state.studentId,
        course_id: state.courseId,
        topic_id: topicId || undefined,
        concept_id: conceptId || undefined,
        misconception_id: misconceptionId || undefined,
      }),
    });

    const data = await resp.json();
    if (!resp.ok || !data.success) {
      showError("Failed to generate remediation session. Ensure course materials have been ingested.");
      return;
    }

    state.sessionId = data.session_id;
    state.sessionData = data;
    renderRemediationUI(data);

  } catch (err) {
    showError("Could not connect to backend server.");
  }
}

async function loadExistingSession(sessionId) {
  try {
    const resp = await fetch(`${API_BASE}/remediation/${sessionId}`);
    const data = await resp.json();
    if (!resp.ok || !data.success) {
      showError("Remediation session not found.");
      return;
    }
    state.sessionData = data;
    renderRemediationUI(data);
  } catch (err) {
    showError("Network error loading session.");
  }
}

function renderRemediationUI(data) {
  $("loadingPanel").hidden = true;
  $("sessionPanel").hidden = false;

  // Prerequisite Notice
  if (data.prereq_note) {
    $("prereqText").textContent = data.prereq_note;
    $("prereqCallout").hidden = false;
  }

  // Header
  $("topicBadge").textContent = `${data.topic_name || "General"} — ${data.concept_name || "Concept"}`;
  $("remTitle").textContent = data.misconception_title ? `Remediation: ${data.misconception_title}` : `Remediation: ${data.concept_name}`;

  if (data.misconception_title) {
    $("misconceptionSubtitle").textContent = `Addressing identified misunderstanding pattern: "${data.misconception_title}"`;
    $("misconceptionSubtitle").hidden = false;
  }

  // Corrective Explanation
  $("explanationText").textContent = data.corrective_explanation || data.explanation || "";
  $("conceptSummaryBox").textContent = data.correct_concept_summary ? `Key Principle: ${data.correct_concept_summary}` : "";

  // Activities Breakdown
  const activities = data.activities || [];

  // Comparison
  const compAct = activities.find((a) => a.activity_type === "comparison");
  if (compAct && compAct.activity_data) {
    $("mistakenText").textContent = compAct.activity_data.mistaken_approach || "Confounding physical variables.";
    $("correctText").textContent = compAct.activity_data.correct_approach || "Applying definition and formula directly.";
    $("takeawayBanner").textContent = compAct.activity_data.key_takeaway ? `💡 Key Takeaway: ${compAct.activity_data.key_takeaway}` : "";
    $("comparisonSection").hidden = false;
  }

  // Worked Example
  const exampleAct = activities.find((a) => a.activity_type === "worked_example");
  if (exampleAct && exampleAct.activity_data) {
    $("exampleProblem").textContent = exampleAct.activity_data.problem || "";
    const stepsList = $("exampleSteps");
    stepsList.innerHTML = "";
    (exampleAct.activity_data.solution_steps || []).forEach((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      stepsList.appendChild(li);
    });
    $("workedExampleSection").hidden = false;
  }

  // Citations
  renderCitations(data.source_refs || []);

  // Self Check
  const checkAct = activities.find((a) => a.activity_type === "self_check");
  if (checkAct && checkAct.activity_data) {
    renderSelfCheck(checkAct.activity_data);
    $("selfCheckSection").hidden = false;
  }

  // Practice Question
  const practiceAct = activities.find((a) => a.activity_type === "practice_question");
  if (practiceAct && practiceAct.activity_data) {
    renderPracticeQuestion(practiceAct.activity_data);
    $("practiceSection").hidden = false;
  }

  // Complete button
  $("completeSessionBtn").addEventListener("click", completeSession);
}

function renderCitations(refs) {
  const list = $("citationList");
  list.innerHTML = "";
  if (!refs || refs.length === 0) {
    list.innerHTML = "<li>Course general material</li>";
    return;
  }

  refs.forEach((r) => {
    const li = document.createElement("li");
    let parts = [r.file_name || "Course Material"];
    if (r.page) parts.push(`Page ${r.page}`);
    if (r.slide) parts.push(`Slide ${r.slide}`);
    if (r.timestamp_start) parts.push(`@ ${r.timestamp_start}`);
    li.textContent = `📖 ${parts.join(" — ")}`;
    list.appendChild(li);
  });
}

function renderSelfCheck(data) {
  $("selfCheckPrompt").textContent = data.question || "";
  const optsContainer = $("selfCheckOptions");
  optsContainer.innerHTML = "";

  (data.options || []).forEach((optText, idx) => {
    const btn = document.createElement("button");
    btn.textContent = `${idx + 1}. ${optText}`;
    btn.addEventListener("click", () => {
      const isCorrect = idx === (data.correct_option_index || 0);
      const fb = $("selfCheckFeedback");
      fb.style.background = isCorrect ? "#f0fdf4" : "#fef2f2";
      fb.style.color = isCorrect ? "#166534" : "#991b1b";
      fb.style.border = `1px solid ${isCorrect ? "#bbf7d0" : "#fecaca"}`;
      fb.innerHTML = isCorrect
        ? `✓ <strong>Correct!</strong> ${escHtml(data.explanation || "")}`
        : `✗ <strong>Not quite.</strong> ${escHtml(data.explanation || "Review the correct concept above.")}`;
      fb.hidden = false;
    });
    optsContainer.appendChild(btn);
  });
}

function renderPracticeQuestion(qdata) {
  $("practicePrompt").textContent = qdata.prompt || "";
  const grid = $("practiceOptionsGrid");
  grid.innerHTML = "";
  let selectedKey = null;

  (qdata.options || []).forEach((opt) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.style.padding = "0.6rem";
    btn.style.textAlign = "left";
    btn.style.cursor = "pointer";
    btn.innerHTML = `<strong>${opt.key}.</strong> ${escHtml(opt.text)}`;
    btn.addEventListener("click", () => {
      grid.querySelectorAll(".option-btn").forEach((b) => (b.style.borderColor = "#cbd5e1"));
      btn.style.borderColor = "#0284c7";
      selectedKey = opt.key;
    });
    grid.appendChild(btn);
  });

  $("submitPracticeBtn").onclick = () => {
    if (!selectedKey) return;
    const fb = $("practiceFeedbackBox");
    fb.innerHTML = `✓ Answer recorded! Continue practice on your adaptive dashboard.`;
    fb.hidden = false;
  };
}

async function completeSession() {
  try {
    const resp = await fetch(`${API_BASE}/remediation/${state.sessionId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: state.studentId }),
    });
    const data = await resp.json();
    if (data.success) {
      alert("Remediation Session Completed! Great job reinforcing this concept.");
      window.location.href = "dashboard.html";
    }
  } catch (_) {
    alert("Could not update completion status.");
  }
}

function showError(msg) {
  $("loadingPanel").innerHTML = `<div style="color: #dc2626; padding: 1.5rem; text-align: center;">⚠️ ${msg}</div>`;
}

function escHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
