/* ==========================================================================
   VIDYA-X AI — AI Tutor Client Logic (Step 15)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initTutorContext();
  setupTutorEvents();
});

function initTutorContext() {
  const ctx = window.VidyaAPI ? window.VidyaAPI.getContext() : { courseName: "General Course" };
  const pill = document.getElementById("headerCourseName");
  if (pill) pill.textContent = ctx.courseName;

  const demoBanner = document.getElementById("demoBanner");
  if (demoBanner && window.VidyaAPI && window.VidyaAPI.isDemoMode()) {
    demoBanner.style.display = "flex";
  }

  const exitBtn = document.getElementById("exitDemoBtn");
  if (exitBtn) {
    exitBtn.addEventListener("click", () => {
      window.VidyaAPI.disableDemoMode();
      window.location.reload();
    });
  }
}

function setupTutorEvents() {
  const form = document.getElementById("tutorForm");
  const input = document.getElementById("tutorInput");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;

    input.value = "";
    appendUserMessage(q);
    await askTutorQuestion(q);
  });

  // Suggested prompts
  document.querySelectorAll(".prompt-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-q");
      if (q) {
        appendUserMessage(q);
        askTutorQuestion(q);
      }
    });
  });
}

function appendUserMessage(text) {
  const messages = document.getElementById("chatMessages");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble user-bubble";
  bubble.innerHTML = `
    <div class="bubble-header">
      <strong>You</strong>
      <span class="time-stamp">Just now</span>
    </div>
    <p>${escapeHTML(text)}</p>
  `;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

async function askTutorQuestion(question) {
  const messages = document.getElementById("chatMessages");
  const loadingBubble = document.createElement("div");
  loadingBubble.className = "chat-bubble bot-bubble";
  loadingBubble.innerHTML = `
    <div class="bubble-header">
      <strong>VIDYA-X Tutor</strong>
      <span class="time-stamp">Searching course materials...</span>
    </div>
    <p><em>Retrieving verified course citations &amp; generating grounded answer...</em></p>
  `;
  messages.appendChild(loadingBubble);
  messages.scrollTop = messages.scrollHeight;

  try {
    const res = await window.VidyaAPI.askTutor(question);
    loadingBubble.remove();

    if (res.success) {
      appendBotMessage(res.answer, res.supported, res.citations || []);
      renderCitations(res.citations || []);
    } else {
      appendBotMessage(`Error: ${res.error || "Could not retrieve answer from tutor service."}`, false, []);
    }
  } catch (err) {
    loadingBubble.remove();
    appendBotMessage(`Request failed: ${err.message}`, false, []);
  }
}

function appendBotMessage(answer, supported, citations) {
  const messages = document.getElementById("chatMessages");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble bot-bubble";

  let bodyHtml = "";
  if (!supported) {
    bodyHtml = `<div class="abstention-box">⚠️ ${escapeHTML(answer)}</div>`;
  } else {
    // Format citation brackets [1], [2] as clickable tags
    let formatted = escapeHTML(answer);
    formatted = formatted.replace(/\[(\d+)\]/g, '<span class="citation-pill" data-cite="$1">[$1]</span>');
    bodyHtml = `<p>${formatted.replace(/\n\n/g, "</p><p>")}</p>`;
  }

  bubble.innerHTML = `
    <div class="bubble-header">
      <strong>VIDYA-X Tutor</strong>
      <span class="time-stamp">Just now</span>
    </div>
    ${bodyHtml}
  `;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;

  // Click citation to highlight in sidebar
  bubble.querySelectorAll(".citation-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const idx = pill.getAttribute("data-cite");
      const targetCard = document.getElementById(`cite-card-${idx}`);
      if (targetCard) {
        targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
        targetCard.style.outline = "2px solid var(--primary-color)";
        setTimeout(() => (targetCard.style.outline = "none"), 2000);
      }
    });
  });
}

function renderCitations(citations) {
  const list = document.getElementById("citationsList");
  if (!citations || citations.length === 0) {
    list.innerHTML = `
      <div class="citation-empty">
        <span>⚠️</span>
        <p>No verified course citations found for this query.</p>
      </div>
    `;
    return;
  }

  list.innerHTML = citations
    .map(
      (c, i) => `
    <div class="citation-card" id="cite-card-${i + 1}">
      <div class="citation-meta">
        <span>${escapeHTML(c.citation_id)} ${escapeHTML(c.file_name)}</span>
        <span>${escapeHTML(c.location)}</span>
      </div>
      <p class="citation-excerpt">${escapeHTML(c.excerpt)}</p>
    </div>
  `
    )
    .join("");
}

function escapeHTML(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
