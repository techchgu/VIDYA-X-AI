/* ==========================================================================
   VIDYA-X AI — Visual Intelligence Studio Logic (Step 14)
   ========================================================================== */

const API_BASE = "http://localhost:8000/api";
const STORAGE_KEY = "vidyaXProfile";

let currentCourseId = "General";
let currentVisuals = [];

document.addEventListener("DOMContentLoaded", () => {
  initProfileContext();
  checkVisionProvider();
  loadCourseMaterials();
  loadVisuals();
  setupEventHandlers();
});

function initProfileContext() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      if (p.courseId) currentCourseId = p.courseId;
      else if (p.courseName) currentCourseId = `course_${slugify(p.courseName)}`;
    }
  } catch (_) {}
}

function slugify(text) {
  return (text || "general")
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[-\s]+/g, "_");
}

async function checkVisionProvider() {
  const badge = document.getElementById("providerBadge");
  const dot = badge ? badge.querySelector(".badge-dot") : null;
  const text = document.getElementById("providerText");

  try {
    const res = await fetch(`${API_BASE}/visuals/provider-info`);
    const data = await res.json();
    if (res.ok && data.success) {
      if (data.vision_available) {
        if (dot) dot.className = "badge-dot active";
        if (text) text.textContent = `Vision AI Online (${data.vision_model})`;
      } else {
        if (dot) dot.className = "badge-dot offline";
        if (text) text.textContent = "Offline Vision (Local Structural Descriptors)";
      }
    }
  } catch (_) {
    if (text) text.textContent = "Vision Service Standby";
  }
}

async function loadVisuals() {
  showLoading(true);
  const filterSource = document.getElementById("filterSource").value;
  const filterType = document.getElementById("filterAssetType").value;

  let url = `${API_BASE}/courses/${encodeURIComponent(currentCourseId)}/visuals?page_size=50`;
  if (filterSource) url += `&source_type=${encodeURIComponent(filterSource)}`;
  if (filterType) url += `&asset_type=${encodeURIComponent(filterType)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    showLoading(false);

    if (res.ok && data.success && data.assets && data.assets.length > 0) {
      currentVisuals = data.assets;
      renderVisualsGrid(currentVisuals);
      showEmpty(false);
    } else {
      currentVisuals = [];
      renderVisualsGrid([]);
      showEmpty(true);
    }
  } catch (err) {
    showLoading(false);
    showEmpty(true);
  }
}

async function searchVisuals(query) {
  if (!query || !query.trim()) {
    document.getElementById("searchNotice").style.display = "none";
    loadVisuals();
    return;
  }

  showLoading(true);
  const notice = document.getElementById("searchNotice");
  const noticeText = document.getElementById("searchNoticeText");
  notice.style.display = "block";
  noticeText.textContent = `Searching visual knowledge for: "${query}"...`;

  try {
    const res = await fetch(
      `${API_BASE}/courses/${encodeURIComponent(currentCourseId)}/visuals/search?query=${encodeURIComponent(query)}&top_k=20`
    );
    const data = await res.json();
    showLoading(false);

    if (res.ok && data.success && data.results && data.results.length > 0) {
      noticeText.textContent = `Found ${data.results.length} visual items matching "${query}"`;
      renderSearchResults(data.results);
      showEmpty(false);
    } else {
      noticeText.textContent = `No visual items found matching "${query}"`;
      renderVisualsGrid([]);
      showEmpty(true);
    }
  } catch (err) {
    showLoading(false);
    noticeText.textContent = "Visual search request failed.";
  }
}

function renderVisualsGrid(assets) {
  const grid = document.getElementById("visualsGrid");
  grid.innerHTML = "";

  assets.forEach((item) => {
    const card = document.createElement("div");
    card.className = "visual-card";

    const imgSrc = item.has_image
      ? `${API_BASE}/visuals/assets/${encodeURIComponent(item.id)}/image`
      : "";

    const locTag = item.page_number
      ? `Page ${item.page_number}`
      : item.slide_number
      ? `Slide ${item.slide_number}`
      : item.timestamp_start
      ? `${item.timestamp_start}`
      : item.source_type.toUpperCase();

    card.innerHTML = `
      <div class="visual-thumb-wrapper">
        ${
          imgSrc
            ? `<img class="visual-thumb" src="${imgSrc}" alt="${escapeHTML(item.source_file_name)}" onerror="this.style.display='none'">`
            : `<span style="font-size:2.5rem;">📊</span>`
        }
        <span class="asset-badge">${escapeHTML(item.asset_type.replace(/_/g, " "))}</span>
      </div>
      <div class="visual-info">
        <p class="visual-desc-snippet">${escapeHTML(item.visual_description || "Visual asset")}</p>
        <div class="visual-meta-tags">
          <span>📁 ${escapeHTML(item.source_file_name)}</span>
          <span>📍 ${escapeHTML(locTag)}</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => openDetailModal(item.id));
    grid.appendChild(card);
  });
}

function renderSearchResults(results) {
  const grid = document.getElementById("visualsGrid");
  grid.innerHTML = "";

  results.forEach((r) => {
    const card = document.createElement("div");
    card.className = "visual-card";

    const src = r.source || {};
    const assetId = src.visual_asset_id;
    const imgSrc = assetId
      ? `${API_BASE}/visuals/assets/${encodeURIComponent(assetId)}/image`
      : "";

    const locTag = src.page
      ? `Page ${src.page}`
      : src.slide
      ? `Slide ${src.slide}`
      : src.timestamp_start
      ? `${src.timestamp_start}`
      : (src.source_type || "").toUpperCase();

    const scorePct = Math.round((r.score || 0) * 100);

    card.innerHTML = `
      <div class="visual-thumb-wrapper">
        ${
          imgSrc
            ? `<img class="visual-thumb" src="${imgSrc}" alt="${escapeHTML(src.file_name || '')}" onerror="this.style.display='none'">`
            : `<span style="font-size:2.5rem;">📈</span>`
        }
        <span class="similarity-badge">${scorePct}% match</span>
        <span class="asset-badge">${escapeHTML((src.asset_type || "visual").replace(/_/g, " "))}</span>
      </div>
      <div class="visual-info">
        <p class="visual-desc-snippet">${escapeHTML(r.content || "")}</p>
        <div class="visual-meta-tags">
          <span>📁 ${escapeHTML(src.file_name || "course document")}</span>
          <span>📍 ${escapeHTML(locTag)}</span>
        </div>
      </div>
    `;

    if (assetId) {
      card.addEventListener("click", () => openDetailModal(assetId));
    }
    grid.appendChild(card);
  });
}

async function openDetailModal(assetId) {
  const modal = document.getElementById("detailModal");
  modal.style.display = "flex";

  try {
    const res = await fetch(
      `${API_BASE}/courses/${encodeURIComponent(currentCourseId)}/visuals/${encodeURIComponent(assetId)}`
    );
    const data = await res.json();
    if (res.ok && data.success && data.asset) {
      const a = data.asset;
      const s = a.structured_description || {};

      document.getElementById("detailTitle").textContent =
        s.title || `${a.asset_type.replace(/_/g, " ").toUpperCase()} Detail`;

      const img = document.getElementById("detailImage");
      const fallback = document.getElementById("detailImageFallback");
      if (a.has_image) {
        img.src = `${API_BASE}/visuals/assets/${encodeURIComponent(a.id)}/image`;
        img.style.display = "block";
        fallback.style.display = "none";
      } else {
        img.style.display = "none";
        fallback.style.display = "flex";
      }

      const locParts = [a.source_file_name];
      if (a.page_number) locParts.push(`Page ${a.page_number}`);
      if (a.slide_number) locParts.push(`Slide ${a.slide_number}`);
      if (a.timestamp_start) locParts.push(`At ${a.timestamp_start}`);
      document.getElementById("detailCitation").textContent = `📌 Citation: ${locParts.join(" • ")}`;

      document.getElementById("detailDescription").textContent =
        s.summary || a.visual_description || "Description unavailable.";

      // Labels
      const labelsBlock = document.getElementById("detailLabelsBlock");
      const labelsContainer = document.getElementById("detailLabels");
      if (s.labels && s.labels.length > 0) {
        labelsBlock.style.display = "block";
        labelsContainer.innerHTML = s.labels
          .map((l) => `<span class="tag-chip">${escapeHTML(l.text || l)}</span>`)
          .join("");
      } else {
        labelsBlock.style.display = "none";
      }

      // Relationships
      const relsBlock = document.getElementById("detailRelsBlock");
      const relsList = document.getElementById("detailRels");
      if (s.relationships && s.relationships.length > 0) {
        relsBlock.style.display = "block";
        relsList.innerHTML = s.relationships
          .map((r) => `<li><strong>${escapeHTML(r.from)}</strong> &rarr; <em>${escapeHTML(r.relation)}</em> &rarr; <strong>${escapeHTML(r.to)}</strong></li>`)
          .join("");
      } else {
        relsBlock.style.display = "none";
      }

      // Equations
      const eqBlock = document.getElementById("detailEquationsBlock");
      const eqBox = document.getElementById("detailEquations");
      if (s.equations && s.equations.length > 0) {
        eqBlock.style.display = "block";
        eqBox.innerHTML = s.equations
          .map((e) => `<div style="font-family:monospace; margin-bottom:4px; padding:4px 8px; background:#f1f5f9; border-radius:4px;">${escapeHTML(String(e))}</div>`)
          .join("");
      } else {
        eqBlock.style.display = "none";
      }

      // Source meta grid
      const metaGrid = document.getElementById("detailSourceMeta");
      metaGrid.innerHTML = `
        <div style="font-size:0.85rem; color:#475569;">
          <p><strong>File:</strong> ${escapeHTML(a.source_file_name)}</p>
          <p><strong>Format:</strong> ${escapeHTML(a.source_type.toUpperCase())}</p>
          <p><strong>Status:</strong> ${escapeHTML(a.processing_status)}</p>
          ${a.knowledge_chunk_id ? `<p><strong>Indexed Vector Chunk:</strong> <code>${escapeHTML(a.knowledge_chunk_id)}</code></p>` : ""}
        </div>
      `;
    }
  } catch (err) {
    document.getElementById("detailDescription").textContent = "Could not load asset details.";
  }
}

async function loadCourseMaterials() {
  const sel = document.getElementById("materialSelect");
  try {
    const res = await fetch(`${API_BASE}/courses/${encodeURIComponent(currentCourseId)}/concepts`);
    // Alternatively fetch from upload tracking or use materials
    sel.innerHTML = `<option value="">Select a material file below</option>`;
  } catch (_) {}

  // Also query materials directly via endpoint if exists, else load uploaded files
  try {
    const res = await fetch(`${API_BASE}/courses/${encodeURIComponent(currentCourseId)}/visuals?page_size=1`);
    // Fallback populated via prompt
  } catch (_) {}
}

function setupEventHandlers() {
  const searchInput = document.getElementById("visualSearchInput");
  const searchBtn = document.getElementById("visualSearchBtn");
  const clearBtn = document.getElementById("clearSearchBtn");

  searchBtn.addEventListener("click", () => {
    const q = searchInput.value.trim();
    if (q) {
      clearBtn.style.display = "inline-block";
      searchVisuals(q);
    }
  });

  searchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      searchBtn.click();
    }
  });

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    clearBtn.style.display = "none";
    document.getElementById("searchNotice").style.display = "none";
    loadVisuals();
  });

  document.getElementById("filterSource").addEventListener("change", loadVisuals);
  document.getElementById("filterAssetType").addEventListener("change", loadVisuals);

  // Modals
  document.getElementById("closeDetailBtn").addEventListener("click", () => {
    document.getElementById("detailModal").style.display = "none";
  });

  document.getElementById("processVisualsBtn").addEventListener("click", () => {
    const matId = prompt("Enter Material ID to process for visual understanding (or leave blank to process all in uploads):");
    if (matId !== null) {
      triggerVisualProcessing(matId.trim());
    }
  });
}

async function triggerVisualProcessing(matId) {
  if (!matId) {
    alert("Please provide a valid material ID to process.");
    return;
  }

  const notice = document.getElementById("searchNotice");
  const noticeText = document.getElementById("searchNoticeText");
  notice.style.display = "block";
  noticeText.textContent = `Processing visuals for material ${matId}...`;

  try {
    const res = await fetch(`${API_BASE}/visuals/process/${encodeURIComponent(matId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skip_vision: false }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      alert(`Success! Processed ${data.images_processed || 0} visual assets (${data.chunks_created || 0} vector chunks created).`);
      notice.style.display = "none";
      loadVisuals();
    } else {
      alert(`Visual processing failed: ${data.error || "Unknown error"}`);
    }
  } catch (err) {
    alert(`Request error: ${err.message}`);
  }
}

function showLoading(show) {
  const el = document.getElementById("loadingIndicator");
  if (el) el.style.display = show ? "block" : "none";
}

function showEmpty(show) {
  const el = document.getElementById("emptyState");
  if (el) el.style.display = show ? "block" : "none";
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
