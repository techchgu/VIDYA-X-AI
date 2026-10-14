/**
 * VIDYA-X AI — Flashcards Studio JavaScript (Step 11)
 * Handles active-recall flashcard practice, deck generation, card flipping, shuffling, and review ratings.
 */

"use strict";

const API_BASE = "http://localhost:8000/api";

let state = {
  studentId: "student_demo",
  courseId: "general",
  preferredLanguage: "English",
  currentDeck: null,
  cards: [],
  currentIndex: 0,
  isRevealed: false,
  ratingsCount: { again: 0, hard: 0, good: 0, easy: 0 },
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", function () {
  loadProfileAndCourse();
  setupEventListeners();
  loadCourseTopics();
  loadSavedDecks();
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
  const form = $("deckForm");
  if (form) form.addEventListener("submit", handleGenerateDeckSubmit);

  const cardBox = $("cardBox");
  if (cardBox) cardBox.addEventListener("click", toggleReveal);

  const revealBtn = $("revealBtn");
  if (revealBtn) revealBtn.addEventListener("click", toggleReveal);

  const prevBtn = $("prevCardBtn");
  if (prevBtn) prevBtn.addEventListener("click", prevCard);

  const nextBtn = $("nextCardBtn");
  if (nextBtn) nextBtn.addEventListener("click", nextCard);

  const shuffleBtn = $("shuffleBtn");
  if (shuffleBtn) shuffleBtn.addEventListener("click", shuffleCards);

  const restartBtn = $("restartDeckBtn");
  if (restartBtn) restartBtn.addEventListener("click", restartDeck);

  // Rating buttons
  document.querySelectorAll(".rate-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      rateCard(btn.dataset.rating);
    });
  });
}

async function loadCourseTopics() {
  const topicSel = $("topicSelect");
  if (!topicSel) return;

  try {
    const resp = await fetch(`${API_BASE}/graph/${encodeURIComponent(state.courseId)}`);
    const data = await resp.json();

    if (resp.ok && data.success && data.topics) {
      topicSel.innerHTML = '<option value="">✨ All Course Topics (Adaptive)</option>';
      data.topics.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = t.name;
        topicSel.appendChild(opt);
      });
    }
  } catch (_) {
    // Keep default topic options
  }
}

async function handleGenerateDeckSubmit(e) {
  e.preventDefault();
  hideDeckFormError();

  const courseId = $("courseIdInput").value.trim();
  const topicId = $("topicSelect").value;
  const count = parseInt($("cardCountInput").value, 10) || 10;
  const language = $("languageSelect").value;

  if (!courseId) {
    showDeckFormError("Please enter a Course ID.");
    return;
  }

  showState("loading");

  try {
    const resp = await fetch(`${API_BASE}/flashcards/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: state.studentId,
        course_id: courseId,
        topic_id: topicId || null,
        card_count: count,
        language: language,
      }),
    });

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      showState("placeholder");
      showDeckFormError(data.error || "Failed to generate flashcard deck.");
      return;
    }

    startDeckViewer(data);
    loadSavedDecks();

  } catch (err) {
    showState("placeholder");
    showDeckFormError("Could not connect to backend server. Make sure it is running on port 8000.");
  }
}

async function loadSavedDecks() {
  const listEl = $("savedDecksList");
  if (!listEl) return;

  try {
    const resp = await fetch(`${API_BASE}/learner/${encodeURIComponent(state.studentId)}/course/${encodeURIComponent(state.courseId)}/flashcards`);
    const data = await resp.json();

    if (!resp.ok || !data.success || !data.decks || data.decks.length === 0) {
      listEl.innerHTML = '<p style="color: #64748b; font-size: 0.85rem;">No saved flashcard decks yet.</p>';
      return;
    }

    listEl.innerHTML = "";
    data.decks.forEach((d) => {
      const item = document.createElement("div");
      item.className = "saved-deck-item";

      const titleSpan = document.createElement("span");
      titleSpan.className = "saved-deck-title";
      titleSpan.textContent = `${d.title} (${d.card_count} cards)`;
      titleSpan.addEventListener("click", () => loadDeckDetail(d.deck_id));

      const delBtn = document.createElement("button");
      delBtn.className = "delete-deck-btn";
      delBtn.innerHTML = "🗑️";
      delBtn.title = "Delete deck";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteDeck(d.deck_id);
      });

      item.appendChild(titleSpan);
      item.appendChild(delBtn);
      listEl.appendChild(item);
    });

  } catch (_) {
    listEl.innerHTML = '<p style="color: #64748b; font-size: 0.85rem;">Failed to load saved decks.</p>';
  }
}

async function loadDeckDetail(deckId) {
  showState("loading");
  try {
    const resp = await fetch(`${API_BASE}/flashcards/deck/${encodeURIComponent(deckId)}`);
    const data = await resp.json();

    if (!resp.ok || !data.success) {
      showState("placeholder");
      showDeckFormError(data.error || "Could not load selected deck.");
      return;
    }

    startDeckViewer(data);
  } catch (_) {
    showState("placeholder");
    showDeckFormError("Failed to fetch deck details.");
  }
}

async function deleteDeck(deckId) {
  if (!confirm("Are you sure you want to delete this flashcard deck?")) return;

  try {
    const resp = await fetch(`${API_BASE}/flashcards/deck/${encodeURIComponent(deckId)}?student_id=${encodeURIComponent(state.studentId)}`, {
      method: "DELETE",
    });

    if (resp.ok) {
      if (state.currentDeck && state.currentDeck.deck_id === deckId) {
        showState("placeholder");
      }
      loadSavedDecks();
    }
  } catch (_) {
    alert("Delete deck operation failed.");
  }
}

function startDeckViewer(deckData) {
  state.currentDeck = deckData;
  state.cards = (deckData.cards || []).slice();
  state.currentIndex = 0;
  state.isRevealed = false;
  state.ratingsCount = { again: 0, hard: 0, good: 0, easy: 0 };

  $("deckTitle").textContent = deckData.title || "Flashcard Deck";
  showState("viewer");
  renderCurrentCard();
}

function renderCurrentCard() {
  if (state.cards.length === 0) {
    showState("summary");
    return;
  }

  const card = state.cards[state.currentIndex];
  const total = state.cards.length;
  const idx = state.currentIndex;

  // Counter & Progress
  $("cardCounter").textContent = `Card ${idx + 1} of ${total}`;
  $("progressFill").style.width = `${((idx + 1) / total) * 100}%`;

  // Front Face
  $("cardTypeBadge").textContent = (card.card_type || "concept").replace(/_/g, " ");
  $("cardPrompt").textContent = card.front || "Empty Prompt";

  // Back Face
  $("cardAnswer").textContent = card.back || "Empty Answer";
  $("cardExplanation").textContent = card.explanation ? `Explanation: ${card.explanation}` : "";

  // Citations
  const citBox = $("cardCitations");
  const citText = $("citationText");
  const citations = card.citations || [];
  if (citations.length > 0 && citations[0].file_name) {
    const c = citations[0];
    let details = [c.file_name];
    if (c.page) details.push(`Page ${c.page}`);
    if (c.slide) details.push(`Slide ${c.slide}`);
    if (c.timestamp_start) details.push(`Time ${c.timestamp_start}`);
    citText.textContent = details.join(" — ");
    citBox.hidden = false;
  } else {
    citBox.hidden = true;
  }

  // Reset Revealed / Rating State
  state.isRevealed = false;
  $("cardBack").hidden = true;
  $("cardFront").hidden = false;
  $("ratingBar").hidden = true;
  $("revealBtn").textContent = "👁️ Reveal Answer";

  // Nav buttons
  $("prevCardBtn").disabled = idx === 0;
  $("nextCardBtn").textContent = idx === total - 1 ? "Finish Deck" : "Next →";
}

function toggleReveal() {
  state.isRevealed = !state.isRevealed;
  $("cardBack").hidden = !state.isRevealed;
  $("ratingBar").hidden = !state.isRevealed;
  $("revealBtn").textContent = state.isRevealed ? "🙈 Hide Answer" : "👁️ Reveal Answer";
}

function prevCard() {
  if (state.currentIndex > 0) {
    state.currentIndex--;
    renderCurrentCard();
  }
}

function nextCard() {
  if (state.currentIndex < state.cards.length - 1) {
    state.currentIndex++;
    renderCurrentCard();
  } else {
    showSummary();
  }
}

function shuffleCards() {
  for (let i = state.cards.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [state.cards[i], state.cards[j]] = [state.cards[j], state.cards[i]];
  }
  state.currentIndex = 0;
  renderCurrentCard();
}

async function rateCard(rating) {
  if (!rating || !state.cards[state.currentIndex]) return;
  const card = state.cards[state.currentIndex];

  state.ratingsCount[rating] = (state.ratingsCount[rating] || 0) + 1;

  // Send rating review to backend
  try {
    await fetch(`${API_BASE}/flashcards/${encodeURIComponent(card.card_id)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: state.studentId,
        rating: rating,
      }),
    });
  } catch (_) {
    // Non-blocking error
  }

  // Move to next card automatically after rating
  nextCard();
}

function showSummary() {
  const statsBox = $("reviewStats");
  if (statsBox) {
    statsBox.innerHTML = `
      <div class="stat-box"><div class="stat-num" style="color:#ef4444;">${state.ratingsCount.again}</div><div class="stat-lbl">Again</div></div>
      <div class="stat-box"><div class="stat-num" style="color:#ea580c;">${state.ratingsCount.hard}</div><div class="stat-lbl">Hard</div></div>
      <div class="stat-box"><div class="stat-num" style="color:#16a34a;">${state.ratingsCount.good}</div><div class="stat-lbl">Good</div></div>
      <div class="stat-box"><div class="stat-num" style="color:#0284c7;">${state.ratingsCount.easy}</div><div class="stat-lbl">Easy</div></div>
    `;
  }
  showState("summary");
}

function restartDeck() {
  if (state.currentDeck) {
    startDeckViewer(state.currentDeck);
  }
}

function showState(stateName) {
  $("placeholderState").hidden = stateName !== "placeholder";
  $("loadingState").hidden = stateName !== "loading";
  $("deckViewer").hidden = stateName !== "viewer";
  $("summaryCard").hidden = stateName !== "summary";
}

function showDeckFormError(msg) {
  const el = $("deckFormError");
  if (el) {
    el.textContent = msg;
    el.hidden = false;
  }
}

function hideDeckFormError() {
  const el = $("deckFormError");
  if (el) {
    el.textContent = "";
    el.hidden = true;
  }
}
