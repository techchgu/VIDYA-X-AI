/**
 * VIDYA-X AI — Revision Studio JavaScript (Step 11)
 * Handles generating, rendering, listing, and deleting course-grounded revision materials.
 */

"use strict";

const API_BASE = "http://localhost:8000/api";

let state = {
  studentId: "student_demo",
  courseId: "general",
  preferredLanguage: "English",
  currentMaterial: null,
};

const $ = (id) => document.getElementById(id);

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", function () {
  loadProfileAndCourse();
  setupEventListeners();
  loadCourseTopics();
  loadSavedMaterials();
});

function loadProfileAndCourse() {
  try {
    const raw = localStorage.getItem("vidyaXProfile");
    if (raw) {
      const p = JSON.parse(raw);
      if (p.studentId) state.studentId = p.studentId;
      if (p.courseId || p.courseName) state.courseId = p.courseId || p.courseName;
      if (p.preferredLanguage) state.preferredLanguage = p.preferredLanguage;
    }

    const materialsRaw = localStorage.getItem("vidyaXMaterials");
    if (materialsRaw) {
      const mats = JSON.parse(materialsRaw);
      if (mats.length > 0 && mats[0].courseId) {
        state.courseId = mats[0].courseId;
      }
    }

    // Pre-fill inputs
    const cInput = $("courseIdInput");
    if (cInput) cInput.value = state.courseId;

    const langSel = $("languageSelect");
    if (langSel && state.preferredLanguage) {
      langSel.value = state.preferredLanguage;
    }
  } catch (_) {
    // Ignore storage parse error
  }
}

function setupEventListeners() {
  const form = $("revisionForm");
  if (form) {
    form.addEventListener("submit", handleGenerateSubmit);
  }
}

async function loadCourseTopics() {
  const topicSel = $("topicSelect");
  if (!topicSel) return;

  try {
    const resp = await fetch(`${API_BASE}/graph/${encodeURIComponent(state.courseId)}`);
    const data = await resp.json();

    if (resp.ok && data.success && data.topics) {
      topicSel.innerHTML = '<option value="">✨ All Topics (Adaptive / Personalized)</option>';
      data.topics.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = t.name;
        topicSel.appendChild(opt);
      });
    }
  } catch (_) {
    // Keep default options
  }
}

async function handleGenerateSubmit(e) {
  e.preventDefault();
  hideFormError();

  const courseId = $("courseIdInput").value.trim();
  const topicId = $("topicSelect").value;
  const materialType = $("materialTypeSelect").value;
  const depth = $("depthSelect").value;
  const language = $("languageSelect").value;

  if (!courseId) {
    showFormError("Please enter a Course ID.");
    return;
  }

  showState("loading");

  try {
    const resp = await fetch(`${API_BASE}/revision/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: state.studentId,
        course_id: courseId,
        topic_id: topicId || null,
        material_type: materialType,
        language: language,
        depth: depth,
      }),
    });

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      showState("placeholder");
      showFormError(data.error || "Failed to generate revision material.");
      return;
    }

    state.currentMaterial = data;
    renderResourceView(data);
    showState("resource");
    loadSavedMaterials();

  } catch (err) {
    showState("placeholder");
    showFormError("Could not connect to backend server. Make sure it is running on port 8000.");
  }
}

async function loadSavedMaterials() {
  const listEl = $("savedMaterialsList");
  if (!listEl) return;

  try {
    const resp = await fetch(`${API_BASE}/learner/${encodeURIComponent(state.studentId)}/course/${encodeURIComponent(state.courseId)}/revision`);
    const data = await resp.json();

    if (!resp.ok || !data.success || !data.materials || data.materials.length === 0) {
      listEl.innerHTML = '<p style="color: #64748b; font-size: 0.85rem;">No saved materials yet.</p>';
      return;
    }

    listEl.innerHTML = "";
    data.materials.forEach((m) => {
      const item = document.createElement("div");
      item.className = "saved-item";

      const titleLink = document.createElement("span");
      titleLink.className = "saved-item-title";
      titleLink.textContent = m.title;
      titleLink.addEventListener("click", () => loadMaterialDetail(m.material_id));

      const delBtn = document.createElement("button");
      delBtn.className = "delete-btn";
      delBtn.innerHTML = "🗑️";
      delBtn.title = "Delete resource";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteMaterial(m.material_id);
      });

      item.appendChild(titleLink);
      item.appendChild(delBtn);
      listEl.appendChild(item);
    });

  } catch (_) {
    listEl.innerHTML = '<p style="color: #64748b; font-size: 0.85rem;">Failed to load saved library.</p>';
  }
}

async function loadMaterialDetail(matId) {
  showState("loading");
  try {
    const resp = await fetch(`${API_BASE}/revision/${encodeURIComponent(matId)}?student_id=${encodeURIComponent(state.studentId)}`);
    const data = await resp.json();

    if (!resp.ok || !data.success) {
      showState("placeholder");
      showFormError(data.error || "Could not load selected material.");
      return;
    }

    state.currentMaterial = data;
    renderResourceView(data);
    showState("resource");
  } catch (_) {
    showState("placeholder");
    showFormError("Failed to fetch material details.");
  }
}

async function deleteMaterial(matId) {
  if (!confirm("Are you sure you want to delete this revision material?")) return;

  try {
    const resp = await fetch(`${API_BASE}/revision/${encodeURIComponent(matId)}?student_id=${encodeURIComponent(state.studentId)}`, {
      method: "DELETE",
    });

    if (resp.ok) {
      if (state.currentMaterial && state.currentMaterial.material_id === matId) {
        showState("placeholder");
      }
      loadSavedMaterials();
    }
  } catch (_) {
    alert("Delete operation failed.");
  }
}

function renderResourceView(mat) {
  const content = mat.content || {};

  // Title & Badges
  $("resTitle").textContent = mat.title || content.title || "Revision Material";
  $("resBadge").textContent = (mat.material_type || "revision").replace(/_/g, " ");

  $("resMeta").textContent = `Depth: ${mat.depth || "standard"} | Language: ${mat.language || "English"} | Grounded: ${mat.grounded ? "✓ Yes" : "Fallback"}`;

  // Personalization Banner
  const pBanner = $("personalizationBanner");
  const pSummary = mat.personalization || {};
  if (pSummary.reasons && pSummary.reasons.length > 0) {
    $("personalizationTitle").textContent = `⚡ Adaptive Personalization (${pSummary.mode || "tailored"})`;
    $("personalizationReasons").textContent = pSummary.reasons.join(" • ");
    pBanner.hidden = false;
  } else {
    pBanner.hidden = true;
  }

  // Overview
  const ov = $("resOverview");
  if (content.overview) {
    ov.textContent = content.overview;
    ov.hidden = false;
  } else {
    ov.hidden = true;
  }

  // Sections
  const secContainer = $("resSections");
  secContainer.innerHTML = "";
  (content.sections || []).forEach((sec) => {
    const card = document.createElement("div");
    card.className = "res-section-card";

    const heading = document.createElement("h4");
    heading.textContent = sec.heading || "Section";
    card.appendChild(heading);

    if (sec.content) {
      const p = document.createElement("p");
      p.style.lineHeight = "1.6";
      p.style.color = "#334155";
      p.textContent = sec.content;
      card.appendChild(p);
    }

    if (sec.key_points && sec.key_points.length > 0) {
      const ul = document.createElement("ul");
      ul.className = "res-key-points";
      sec.key_points.forEach((kp) => {
        const li = document.createElement("li");
        li.textContent = kp;
        ul.appendChild(li);
      });
      card.appendChild(ul);
    }

    if (sec.citations && sec.citations.length > 0) {
      const citRow = document.createElement("div");
      citRow.className = "citations-row";
      sec.citations.forEach((c) => {
        const chip = document.createElement("span");
        chip.className = "citation-chip";
        chip.textContent = `📍 ${c.source_id || c.file_name || "Course Source"}`;
        citRow.appendChild(chip);
      });
      card.appendChild(citRow);
    }

    secContainer.appendChild(card);
  });

  // Comparison Matrix
  const compWrap = $("comparisonWrap");
  const compBox = $("comparisonBox");
  if (content.comparison_matrix && content.comparison_matrix.length > 0) {
    compBox.innerHTML = "";
    content.comparison_matrix.forEach((cm) => {
      const cCard = document.createElement("div");
      cCard.className = "comparison-card";
      cCard.innerHTML = `
        <div style="font-weight: 700; color: #1e293b; margin-bottom: 0.35rem;">${escapeHTML(cm.concept_a || "")} vs. ${escapeHTML(cm.concept_b || "")}</div>
        <div style="font-size: 0.9rem; color: #475569;">${escapeHTML(cm.distinction || "")}</div>
      `;
      compBox.appendChild(cCard);
    });
    compWrap.hidden = false;
  } else {
    compWrap.hidden = true;
  }

  // Misconception Corrections
  const misWrap = $("misconceptionsWrap");
  const misList = $("misconceptionsList");
  if (content.misconception_corrections && content.misconception_corrections.length > 0) {
    misList.innerHTML = "";
    content.misconception_corrections.forEach((mc) => {
      const mCard = document.createElement("div");
      mCard.className = "misconception-card-res";
      mCard.innerHTML = `
        <div style="font-weight: 700; color: #9b2c2c; margin-bottom: 0.25rem;">❌ Common Error: ${escapeHTML(mc.mistake_title || "")}</div>
        <div style="font-weight: 600; color: #276749; margin-bottom: 0.35rem;">✓ Correct Approach: ${escapeHTML(mc.correct_view || "")}</div>
        <div style="font-size: 0.85rem; color: #742a2a;">${escapeHTML(mc.explanation || "")}</div>
      `;
      misList.appendChild(mCard);
    });
    misWrap.hidden = false;
  } else {
    misWrap.hidden = true;
  }

  // Self Check
  const scWrap = $("selfCheckWrap");
  const scList = $("selfCheckList");
  if (content.self_check && content.self_check.length > 0) {
    scList.innerHTML = "";
    content.self_check.forEach((sc, i) => {
      const scCard = document.createElement("div");
      scCard.className = "self-check-card";
      scCard.innerHTML = `
        <div style="font-weight: 700; color: #166534; margin-bottom: 0.25rem;">Q${i+1}: ${escapeHTML(sc.question || "")}</div>
        <div style="font-size: 0.9rem; color: #15803d;"><strong>Answer:</strong> ${escapeHTML(sc.answer || "")}</div>
      `;
      scList.appendChild(scCard);
    });
    scWrap.hidden = false;
  } else {
    scWrap.hidden = true;
  }

  // Verified Sources
  const sourcesWrap = $("sourcesWrap");
  const sourcesList = $("sourcesList");
  const sourcesData = mat.sources || [];
  if (sourcesData.length > 0) {
    sourcesList.innerHTML = "";
    sourcesData.forEach((s) => {
      const li = document.createElement("li");
      let details = [s.file_name || "Course Document"];
      if (s.page) details.push(`Page ${s.page}`);
      if (s.slide) details.push(`Slide ${s.slide}`);
      if (s.timestamp_start) details.push(`Time ${s.timestamp_start}`);
      li.textContent = details.join(" — ");
      sourcesList.appendChild(li);
    });
    sourcesWrap.hidden = false;
  } else {
    sourcesWrap.hidden = true;
  }
}

function showState(stateName) {
  $("placeholderState").hidden = stateName !== "placeholder";
  $("loadingState").hidden = stateName !== "loading";
  $("resourceView").hidden = stateName !== "resource";
}

function showFormError(msg) {
  const el = $("formError");
  if (el) {
    el.textContent = msg;
    el.hidden = false;
  }
}

function hideFormError() {
  const el = $("formError");
  if (el) {
    el.textContent = "";
    el.hidden = true;
  }
}

function escapeHTML(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
