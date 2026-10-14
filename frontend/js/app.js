/* ============================================
   VIDYA-X AI — app.js  (Step 1)
   ============================================
   This single file handles:
     1. Profile form validation & submission
     2. Saving the profile to localStorage
     3. Rendering saved profile on the dashboard
   It auto-detects which page loaded it.
   ============================================ */

// ── Storage key used across pages ──
const STORAGE_KEY = "vidyaXProfile";

// ── Wait for the DOM to be ready ──
document.addEventListener("DOMContentLoaded", function () {
  // Decide what to run based on which page we're on
  const profileForm = document.getElementById("profileForm");
  const dashboardWelcome = document.getElementById("dashboardWelcome");

  if (profileForm) {
    initProfileForm(profileForm);
  }

  if (dashboardWelcome) {
    renderDashboard(dashboardWelcome);
  }

  // Update the materials count on the dashboard (Step 2)
  var materialsCountEl = document.getElementById("materialsCount");
  if (materialsCountEl) {
    updateMaterialsCount(materialsCountEl);
  }
});

/* =============================================
   PROFILE FORM  (index.html)
   ============================================= */

function initProfileForm(form) {
  form.addEventListener("submit", function (event) {
    event.preventDefault(); // stop default browser submission

    // Clear previous errors
    clearErrors();

    // Collect values
    const studentName = getValue("studentName");
    const courseName = getValue("courseName");
    const preferredLanguage = getValue("preferredLanguage");
    const examDate = getValue("examDate");
    const dailyStudyTime = getValue("dailyStudyTime");

    // Run validation
    let isValid = true;

    if (!studentName) {
      showError("studentNameError", "Please enter your name.");
      markInvalid("studentName");
      isValid = false;
    }

    if (!courseName) {
      showError("courseNameError", "Please enter a course name.");
      markInvalid("courseName");
      isValid = false;
    }

    if (!preferredLanguage) {
      showError("preferredLanguageError", "Please select a language.");
      markInvalid("preferredLanguage");
      isValid = false;
    }

    // Exam date: optional, but must not be in the past if provided
    if (examDate) {
      const today = getTodayDateString();
      if (examDate < today) {
        showError("examDateError", "Exam date cannot be in the past.");
        markInvalid("examDate");
        isValid = false;
      }
    }

    if (!isValid) return; // stop here if any field failed

    // ── Build profile object ──
    const profile = {
      studentName: studentName,
      courseName: courseName,
      preferredLanguage: preferredLanguage,
      examDate: examDate || "",
      dailyStudyTime: dailyStudyTime,
      createdAt: new Date().toISOString(),
    };

    // ── Save to localStorage ──
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));

    // ── Show success message ──
    const successMsg = document.getElementById("successMsg");
    successMsg.classList.add("show");

    // Disable button to prevent double-submit
    document.getElementById("submitBtn").disabled = true;

    // ── Redirect to dashboard after a short delay ──
    setTimeout(function () {
      window.location.href = "pages/dashboard.html";
    }, 1500);
  });
}

/* ── Helper: get trimmed value of an input/select ── */
function getValue(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

/* ── Helper: show an inline error message ── */
function showError(spanId, message) {
  const span = document.getElementById(spanId);
  if (span) span.textContent = message;
}

/* ── Helper: add error styling to a field ── */
function markInvalid(fieldId) {
  const el = document.getElementById(fieldId);
  if (el) el.classList.add("input-error");
}

/* ── Helper: clear all error messages & styles ── */
function clearErrors() {
  // Clear error text
  document.querySelectorAll(".error-msg").forEach(function (span) {
    span.textContent = "";
  });
  // Remove red borders
  document.querySelectorAll(".input-error").forEach(function (el) {
    el.classList.remove("input-error");
  });
}

/* ── Helper: today's date as YYYY-MM-DD string ── */
function getTodayDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return year + "-" + month + "-" + day;
}

/* =============================================
   DASHBOARD  (pages/dashboard.html)
   ============================================= */

function renderDashboard(container) {
  const raw = localStorage.getItem(STORAGE_KEY);

  if (!raw) {
    // No profile found — send user back to create one
    container.innerHTML =
      '<p>No profile found. <a href="../index.html">Create your study profile</a>.</p>';
    return;
  }

  const ctx = window.VidyaAPI ? window.VidyaAPI.getContext() : null;
  const profile = ctx || JSON.parse(raw);

  // Update header context pill
  const headerPill = document.getElementById("headerCourseName");
  if (headerPill) headerPill.textContent = profile.courseName;

  // Toggle demo banner
  const demoBanner = document.getElementById("demoBanner");
  if (demoBanner && window.VidyaAPI && window.VidyaAPI.isDemoMode()) {
    demoBanner.style.display = "flex";
  }

  // Build welcome HTML
  let html = "";
  html += "<h2>Welcome, " + escapeHTML(profile.studentName) + (profile.isDemo ? " (Demo Mode)" : "") + " 👋</h2>";
  html += "<p><strong>Course:</strong> " + escapeHTML(profile.courseName) + "</p>";
  html +=
    "<p><strong>Preferred Language:</strong> " +
    escapeHTML(profile.preferredLanguage || "English") +
    "</p>";
  if (profile.dailyStudyTime) {
    html += "<p><strong>Daily Study Time:</strong> " + escapeHTML(profile.dailyStudyTime) + "</p>";
  }
  if (profile.examDate) {
    html +=
      "<p><strong>Exam Date:</strong> " +
      escapeHTML(formatDate(profile.examDate)) +
      "</p>";
  }

  container.innerHTML = html;

  const studentId = profile.studentId || "student_demo";
  const courseId  = profile.courseId || "general";

  // Update Onboarding checklist items if materials/history exist
  updateOnboardingStatus(studentId, courseId);

  // Load personalized recommendations (Step 9)
  const recBox = document.getElementById("recommendationsBox");
  if (recBox) {
    loadPersonalizedRecommendations(recBox, studentId, courseId);
  }

  // Load active misconceptions (Step 10)
  const needsAttnSec = document.getElementById("needsAttentionSection");
  const misconceptionsBox = document.getElementById("misconceptionsBox");
  if (needsAttnSec && misconceptionsBox) {
    loadActiveMisconceptions(needsAttnSec, misconceptionsBox, studentId, courseId);
  }

  // Load evaluation run summary (Step 13)
  const evalSummaryEl = document.getElementById("evaluationRunSummary");
  if (evalSummaryEl) {
    updateEvaluationRunSummary(evalSummaryEl);
  }

  // Load visual assets count (Step 14)
  const visualsCountEl = document.getElementById("visualsCount");
  if (visualsCountEl) {
    updateVisualsCount(visualsCountEl, courseId);
  }
}

async function updateOnboardingStatus(studentId, courseId) {
  try {
    const res = await window.VidyaAPI.getDashboardSummary();
    if (res.success) {
      if (res.materials_count > 0) {
        const el = document.getElementById("checkMat");
        if (el) { el.textContent = "✓"; el.className = "step-icon step-done"; }
      }
      if (res.has_mastery_history) {
        const el = document.getElementById("checkQuiz");
        if (el) { el.textContent = "✓"; el.className = "step-icon step-done"; }
      }
      if (res.today_tasks_count > 0) {
        const el = document.getElementById("checkPlan");
        if (el) { el.textContent = "✓"; el.className = "step-icon step-done"; }
      }
      const matCard = document.getElementById("materialsCount");
      if (matCard) {
        matCard.textContent = `${res.materials_count} material(s) uploaded (${res.chunks_count} knowledge chunks indexed)`;
      }
    }
  } catch (_) {}
}

async function loadActiveMisconceptions(sectionEl, boxEl, studentId, courseId) {
  try {
    const resp = await fetch(`http://localhost:8000/api/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/misconceptions?status=active`);
    const data = await resp.json();

    if (!resp.ok || !data.success || !data.misconceptions || data.misconceptions.length === 0) {
      sectionEl.hidden = true;
      return;
    }

    let html = `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 0.5rem;">`;

    data.misconceptions.forEach((item) => {
      const confPct = Math.round((item.confidence || 0.5) * 100);
      const statusBadge = item.status === "supported" ? "Confirmed" : "Suspected";
      const statusBg = item.status === "supported" ? "#c53030" : "#dd6b20";

      html += `
        <div style="background: #ffffff; border: 1px solid #feb2b2; border-radius: 8px; padding: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <strong style="color: #9b2c2c; font-size: 0.95rem;">${escapeHTML(item.title)}</strong>
            <span style="font-size: 0.75rem; background: ${statusBg}; color: #ffffff; padding: 0.2rem 0.6rem; border-radius: 12px; font-weight: 600;">${statusBadge}</span>
          </div>
          <p style="margin: 0 0 0.6rem 0; font-size: 0.85rem; color: #4a5568;">${escapeHTML(item.description)}</p>
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #718096; margin-bottom: 0.75rem;">
            <span>Topic: <strong>${escapeHTML(item.topic_name || "General")}</strong></span>
            <span>Confidence: <strong>${confPct}%</strong></span>
          </div>
          <a href="remediation.html?misconception_id=${encodeURIComponent(item.id)}&course_id=${encodeURIComponent(courseId)}" class="btn-primary" style="display: block; text-align: center; font-size: 0.85rem; padding: 0.4rem 0.8rem; text-decoration: none; border-radius: 4px; background: #c53030;">Review Misconception & Remediation →</a>
        </div>
      `;
    });

    html += `</div>`;
    boxEl.innerHTML = html;
    sectionEl.hidden = false;

  } catch (err) {
    sectionEl.hidden = true;
  }
}

async function loadPersonalizedRecommendations(container, studentId, courseId) {
  try {
    const resp = await fetch(`http://localhost:8000/api/personalization/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}`);
    const data = await resp.json();

    if (!resp.ok || !data.success) {
      container.innerHTML = `<p style="color: #64748b;">Complete a few questions first. Your personalized recommendations will appear here.</p>`;
      return;
    }

    if (!data.has_history || !data.recommended_topics || data.recommended_topics.length === 0) {
      container.innerHTML = `
        <div style="background: #f8fafc; border-left: 4px solid #3b82f6; padding: 0.75rem 1rem; border-radius: 4px;">
          <p style="margin: 0 0 0.5rem 0; color: #334155; font-size: 0.95rem;">💡 Complete a few questions first. Your personalized recommendations will appear here.</p>
          <a href="quiz.html?mode=adaptive" class="btn-primary" style="display: inline-block; font-size: 0.85rem; padding: 0.4rem 0.8rem; text-decoration: none; border-radius: 4px;">Start Diagnostic Practice</a>
        </div>
      `;
      return;
    }

    let recHtml = `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 1rem;">`;
    
    data.recommended_topics.slice(0, 3).forEach((topic) => {
      const masteryPct = Math.round((topic.mastery || 0.20) * 100);
      let badgeColor = "#ef4444"; // red (weak)
      let badgeLabel = "Needs Review";

      if (masteryPct >= 80) {
        badgeColor = "#10b981"; // green (mastered)
        badgeLabel = "Mastered";
      } else if (masteryPct >= 50) {
        badgeColor = "#f59e0b"; // yellow (developing)
        badgeLabel = "Developing";
      }

      recHtml += `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.85rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
            <strong style="color: #1e293b; font-size: 0.95rem;">${escapeHTML(topic.topic_name)}</strong>
            <span style="font-size: 0.75rem; background: ${badgeColor}; color: #ffffff; padding: 0.15rem 0.5rem; border-radius: 12px; font-weight: 600;">${badgeLabel}</span>
          </div>
          <p style="margin: 0 0 0.5rem 0; font-size: 0.85rem; color: #64748b;">${escapeHTML(topic.reason)}</p>
          <div style="font-size: 0.85rem; color: #475569; font-weight: 600;">Mastery: ${masteryPct}%</div>
        </div>
      `;
    });

    recHtml += `</div>`;
    recHtml += `<a href="quiz.html?mode=adaptive&course_id=${encodeURIComponent(courseId)}" class="btn-primary" style="display: inline-block; padding: 0.55rem 1.25rem; font-size: 0.9rem; text-decoration: none; border-radius: 6px;">⚡ Start Adaptive Practice Now</a>`;

    container.innerHTML = recHtml;

  } catch (err) {
    container.innerHTML = `<p style="color: #64748b;">Complete a few practice questions to unlock personalized recommendations.</p>`;
  }
}


/* ── Helper: format YYYY-MM-DD to a readable string ── */
function formatDate(isoDate) {
  const parts = isoDate.split("-");
  if (parts.length !== 3) return isoDate;
  const dateObj = new Date(parts[0], parts[1] - 1, parts[2]);
  return dateObj.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/* ── Helper: basic HTML escaping to prevent XSS ── */
function escapeHTML(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

/* ── Helper: update course materials count on dashboard (Step 2) ── */
function updateMaterialsCount(container) {
  const raw = localStorage.getItem("vidyaXMaterials");
  const materials = raw ? JSON.parse(raw) : [];
  const count = materials.length;

  if (count === 1) {
    container.textContent = "1 material uploaded";
  } else {
    container.textContent = count + " materials uploaded";
  }

  // Update Revision, Flashcards, Study Plan & Readiness counts (Step 11 & Step 12)
  const revEl = document.getElementById("revisionCount");
  const fcEl = document.getElementById("flashcardCount");
  const spEl = document.getElementById("todayTasksCount");
  const erEl = document.getElementById("readinessSummary");
  if (revEl || fcEl || spEl || erEl) {
    const rawProf = localStorage.getItem("vidyaXProfile");
    const profile = rawProf ? JSON.parse(rawProf) : {};
    const studentId = profile.studentId || "student_demo";
    const courseId = profile.courseId || profile.courseName || "general";

    if (revEl) updateRevisionCount(revEl, studentId, courseId);
    if (fcEl) updateFlashcardCount(fcEl, studentId, courseId);
    if (spEl) updateStudyPlanCount(spEl, studentId, courseId);
    if (erEl) updateExamReadinessSummary(erEl, studentId, courseId);
  }
}

async function updateRevisionCount(container, studentId, courseId) {
  try {
    const resp = await fetch(`http://localhost:8000/api/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/revision`);
    const data = await resp.json();
    if (resp.ok && data.success && data.materials) {
      const cnt = data.materials.length;
      container.textContent = cnt === 1 ? "1 saved revision guide" : `${cnt} saved revision guides`;
    }
  } catch (_) {
    // Keep default text
  }
}

async function updateFlashcardCount(container, studentId, courseId) {
  try {
    const resp = await fetch(`http://localhost:8000/api/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/flashcards`);
    const data = await resp.json();
    if (resp.ok && data.success && data.decks) {
      const cnt = data.decks.length;
      container.textContent = cnt === 1 ? "1 practice flashcard deck" : `${cnt} practice flashcard decks`;
    }
  } catch (_) {
    // Keep default text
  }
}

async function updateStudyPlanCount(container, studentId, courseId) {
  if (!container) return;
  try {
    const resp = await fetch(`http://localhost:8000/api/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/study-plan/today`);
    const data = await resp.json();
    if (resp.ok && data.success) {
      if (data.has_plan && data.tasks) {
        const pending = data.tasks.filter(t => t.status === 'pending').length;
        container.textContent = pending === 1 ? "1 task planned for today" : `${pending} tasks planned for today`;
      } else {
        container.textContent = "Personalized daily & weekly schedules.";
      }
    }
  } catch (_) {}
}

async function updateExamReadinessSummary(container, studentId, courseId) {
  if (!container) return;
  try {
    const resp = await fetch(`http://localhost:8000/api/learner/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/exam-readiness`);
    const data = await resp.json();
    if (resp.ok && data.success) {
      container.textContent = `Status: ${data.category_label || 'Insufficient Data'} (${Math.round((data.average_mastery || 0) * 100)}% mastery)`;
    }
  } catch (_) {}
}

/* =============================================
   EVALUATION DASHBOARD SUMMARY  (Step 13)
   ============================================= */

async function updateEvaluationRunSummary(container) {
  if (!container) return;
  try {
    const resp = await fetch('http://localhost:8000/api/evaluation/runs');
    const data = await resp.json();
    if (!resp.ok || !data.success || !data.runs || data.runs.length === 0) {
      container.textContent = 'No evaluation runs yet. Click to run a benchmark.';
      return;
    }
    const latest = data.runs[0];
    const ts = latest.timestamp
      ? new Date(latest.timestamp).toLocaleDateString()
      : '—';
    const gateStr = latest.quality_gate_passed === true
      ? '✅ All gates passed'
      : latest.quality_gate_passed === false
        ? '❌ Gate failed'
        : '— Gate unknown';
    container.textContent = `Latest: ${ts} · ${latest.cases_evaluated ?? '?'} cases · ${gateStr}`;
  } catch (_) {
    container.textContent = 'Reproducible quality assessment across all AI components.';
  }
}

/* =============================================
   VISUAL ASSETS SUMMARY (Step 14)
   ============================================= */

async function updateVisualsCount(container, courseId) {
  if (!container) return;
  try {
    const resp = await fetch(`http://localhost:8000/api/courses/${encodeURIComponent(courseId)}/visuals?page_size=1`);
    const data = await resp.json();
    if (resp.ok && data.success) {
      const count = data.total || 0;
      container.textContent = count === 1 ? "1 visual asset indexed" : `${count} visual assets indexed`;
    }
  } catch (_) {
    container.textContent = "Explore diagrams, charts, plots & video frames.";
  }
}
