/* ============================================
   VIDYA-X AI — upload.js  (Step 3)
   ============================================
   Handles:
     1. File selection (click & drag-and-drop)
     2. File validation (extension & size)
     3. Selected-files list with remove button
     4. REAL backend upload & extraction via FastAPI:
        - Sends FormData (file, course_name) to POST /api/upload
        - Real upload progress tracking via XHR
        - Live processing & extraction status display
        - Clean error handling (unsupported, server offline, etc.)
     5. Persistence of structured metadata to localStorage (vidyaXMaterials)
     6. Uploaded materials library with delete capability
   ============================================ */

// ── Configuration & Constants ──
var API_BASE_URL = "http://localhost:8000";
var API_UPLOAD_URL = API_BASE_URL + "/api/upload";
var MATERIALS_KEY = "vidyaXMaterials";
var PROFILE_KEY = "vidyaXProfile";
var MAX_FILE_SIZE = 500 * 1024 * 1024; // 500 MB in bytes
var ALLOWED_EXTENSIONS = [".pdf", ".ppt", ".pptx", ".mp4"];

// ── State: files queued in the UI ──
var selectedFiles = [];

// ── Initialize on page load ──
document.addEventListener("DOMContentLoaded", function () {
  // Ensure the user has created a profile in Step 1
  var profile = getProfile();
  if (!profile) {
    window.location.href = "../index.html";
    return;
  }

  initDropZone();
  initFileInput();
  initUploadButton();
  renderUploadedMaterials();
});

/* =============================================
   PROFILE HELPER
   ============================================= */

function getProfile() {
  var raw = localStorage.getItem(PROFILE_KEY);
  return raw ? JSON.parse(raw) : null;
}

/* =============================================
   DROP ZONE (Drag-and-Drop)
   ============================================= */

function initDropZone() {
  var dropZone = document.getElementById("dropZone");

  // Prevent standard browser drag/drop behaviors
  ["dragenter", "dragover", "dragleave", "drop"].forEach(function (evt) {
    dropZone.addEventListener(evt, function (e) {
      e.preventDefault();
      e.stopPropagation();
    });
  });

  // Visual highlight on hover
  ["dragenter", "dragover"].forEach(function (evt) {
    dropZone.addEventListener(evt, function () {
      dropZone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach(function (evt) {
    dropZone.addEventListener(evt, function () {
      dropZone.classList.remove("drag-over");
    });
  });

  // Handle dropped files
  dropZone.addEventListener("drop", function (e) {
    handleFiles(e.dataTransfer.files);
  });

  // Clicking drop zone opens the hidden file input
  dropZone.addEventListener("click", function (e) {
    if (e.target.id === "chooseBtn") return; // Handled by button click
    document.getElementById("fileInput").click();
  });
}

/* =============================================
   FILE INPUT (Choose Files button)
   ============================================= */

function initFileInput() {
  var fileInput = document.getElementById("fileInput");
  var chooseBtn = document.getElementById("chooseBtn");

  chooseBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    fileInput.click();
  });

  fileInput.addEventListener("change", function () {
    handleFiles(this.files);
    this.value = ""; // Reset to allow re-selection of same file
  });
}

/* =============================================
   HANDLE SELECTED FILES
   ============================================= */

function handleFiles(fileList) {
  for (var i = 0; i < fileList.length; i++) {
    var file = fileList[i];
    var ext = getExtension(file.name);
    var error = validateFile(file, ext);

    // Prevent duplicate entries of the same file
    var isDuplicate = selectedFiles.some(function (f) {
      return f.name === file.name && f.size === file.size;
    });
    if (isDuplicate) continue;

    selectedFiles.push({
      id: generateId(),
      file: file,
      name: file.name,
      extension: ext,
      type: getTypeLabel(ext),
      size: file.size,
      error: error,
      status: error ? "error" : "ready",
      statusText: error ? error : "Ready to upload",
      progress: 0,
      unitsExtracted: null,
      fileId: null,
    });
  }

  renderSelectedFiles();
  updateUploadButton();
}

/* =============================================
   VALIDATION
   ============================================= */

function validateFile(file, ext) {
  if (ALLOWED_EXTENSIONS.indexOf(ext) === -1) {
    return "Unsupported file type. Supported: PDF, PPT, PPTX, MP4";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "File size exceeds the 500 MB limit";
  }
  return null;
}

/* =============================================
   RENDER SELECTED FILES
   ============================================= */

function renderSelectedFiles() {
  var container = document.getElementById("selectedList");
  var section = document.getElementById("selectedSection");

  if (selectedFiles.length === 0) {
    section.style.display = "none";
    container.innerHTML = "";
    return;
  }
  section.style.display = "block";

  var html = "";

  selectedFiles.forEach(function (f) {
    var icon = getFileIcon(f.extension);
    var sizeStr = formatFileSize(f.size);
    var isError = f.status === "error" || f.status === "failed";
    var isUploading = f.status === "uploading";
    var isProcessing = f.status === "processing";
    var isProcessed = f.status === "processed";

    var itemClass = "file-item";
    if (isError) itemClass += " file-item-error";

    html += '<div class="file-item' + (isError ? " file-item-error" : "") + '" data-id="' + f.id + '">';
    html += '  <div class="file-item-row">';
    html += '    <span class="file-item-icon">' + icon + "</span>";
    html += '    <div class="file-item-details">';
    html += '      <span class="file-item-name">' + escapeHTML(f.name) + "</span>";
    html += '      <span class="file-item-meta">' + escapeHTML(f.type) + " &bull; " + sizeStr;
    if (f.unitsExtracted !== null) {
      html += " &bull; " + f.unitsExtracted + " content units";
    }
    html += "      </span>";

    if (f.error) {
      html += '      <span class="file-error-text">' + escapeHTML(f.error) + "</span>";
    }
    html += "    </div>"; // .file-item-details

    // Status label
    var statusClass = "file-item-status";
    if (isProcessed) statusClass += " status-processed";
    else if (isProcessing) statusClass += " status-processing";
    else if (isError) statusClass += " status-failed";

    html += '    <span class="' + statusClass + '">' + escapeHTML(f.statusText) + "</span>";

    // Allow removing before upload, or retrying after failure
    if (!isUploading && !isProcessing && !isProcessed) {
      html += '    <button class="btn-remove" data-id="' + f.id + '" title="Remove">\u2715</button>';
    }

    html += "  </div>"; // .file-item-row

    // Progress bar (shown during upload and processing)
    if (isUploading || isProcessing || isProcessed) {
      html += '  <div class="progress-bar active">';
      html += '    <div class="progress-fill" style="width:' + Math.round(f.progress) + '%"></div>';
      html += "  </div>";
    }

    html += "</div>"; // .file-item
  });

  container.innerHTML = html;

  // Wire up remove buttons
  container.querySelectorAll(".btn-remove").forEach(function (btn) {
    btn.addEventListener("click", function () {
      removeSelectedFile(btn.getAttribute("data-id"));
    });
  });
}

function removeSelectedFile(id) {
  selectedFiles = selectedFiles.filter(function (f) {
    return f.id !== id;
  });
  renderSelectedFiles();
  updateUploadButton();
}

/* =============================================
   UPLOAD BUTTON STATE
   ============================================= */

function initUploadButton() {
  document.getElementById("uploadBtn").addEventListener("click", function () {
    startBackendUpload();
  });
}

function updateUploadButton() {
  var btn = document.getElementById("uploadBtn");
  var pendingFiles = selectedFiles.filter(function (f) {
    return f.status === "ready" || f.status === "failed";
  });

  if (pendingFiles.length === 0) {
    btn.disabled = true;
    btn.textContent = "Upload Materials";
  } else {
    btn.disabled = false;
    btn.textContent = "Upload " + pendingFiles.length + (pendingFiles.length === 1 ? " Material" : " Materials");
  }
}

/* =============================================
   REAL BACKEND UPLOAD & EXTRACTION (FastAPI)
   ============================================= */

function startBackendUpload() {
  var filesToUpload = selectedFiles.filter(function (f) {
    return f.status === "ready" || f.status === "failed";
  });

  if (filesToUpload.length === 0) return;

  var btn = document.getElementById("uploadBtn");
  btn.disabled = true;
  btn.textContent = "Processing Materials\u2026";

  var profile = getProfile();
  var courseName = profile ? profile.courseName : "General";

  var completedCount = 0;

  // Process files sequentially or concurrently
  filesToUpload.forEach(function (fileObj) {
    uploadSingleFile(fileObj, courseName, function () {
      completedCount++;
      if (completedCount === filesToUpload.length) {
        onUploadBatchComplete();
      }
    });
  });
}

function uploadSingleFile(fileObj, courseName, onDone) {
  fileObj.status = "uploading";
  fileObj.statusText = "Uploading\u2026 0%";
  fileObj.progress = 0;
  fileObj.error = null;
  renderSelectedFiles();

  var formData = new FormData();
  formData.append("file", fileObj.file);
  formData.append("course_name", courseName);

  var xhr = new XMLHttpRequest();
  xhr.open("POST", API_UPLOAD_URL, true);

  // 1. Upload progress
  xhr.upload.onprogress = function (e) {
    if (e.lengthComputable) {
      var pct = Math.round((e.loaded / e.total) * 100);
      fileObj.progress = Math.min(pct, 95); // Reserve 95-100% for extraction
      fileObj.statusText = "Uploading\u2026 " + fileObj.progress + "%";
      updateSingleFileItemDOM(fileObj);
    }
  };

  // 2. Upload reached server; backend is now running extraction
  xhr.upload.onload = function () {
    fileObj.status = "processing";
    fileObj.progress = 95;
    fileObj.statusText = "Extracting content\u2026";
    updateSingleFileItemDOM(fileObj);
  };

  // 3. Response received from FastAPI backend
  xhr.onload = function () {
    var responseData = null;
    try {
      responseData = JSON.parse(xhr.responseText);
    } catch (parseErr) {
      responseData = null;
    }

    if (xhr.status >= 200 && xhr.status < 300 && responseData && responseData.success) {
      // Successful extraction
      fileObj.status = "processed";
      fileObj.progress = 100;
      fileObj.fileId = responseData.file_id;
      fileObj.unitsExtracted = responseData.units_extracted;
      fileObj.statusText = "\u2713 Completed (" + responseData.units_extracted + " units)";
      updateSingleFileItemDOM(fileObj);

      // Persist metadata to vidyaXMaterials
      saveMaterialMetadata({
        id: responseData.file_id,
        name: fileObj.name,
        extension: fileObj.extension,
        type: fileObj.type,
        size: fileObj.size,
        courseName: courseName,
        status: "processed",
        fileId: responseData.file_id,
        unitsExtracted: responseData.units_extracted,
        extractionFile: responseData.extraction_file,
        uploadedAt: new Date().toISOString(),
      });
    } else {
      // Backend returned error response (e.g. 400, 422, 500)
      var errorMsg = (responseData && responseData.error)
        ? responseData.error
        : "Extraction failed (Status: " + xhr.status + ")";
      fileObj.status = "failed";
      fileObj.error = errorMsg;
      fileObj.statusText = "\u2715 Failed";
      updateSingleFileItemDOM(fileObj);
    }
    onDone();
  };

  // 4. Network or connectivity error (e.g. backend server is not running)
  xhr.onerror = function () {
    fileObj.status = "failed";
    fileObj.error = "Backend server not reached at " + API_BASE_URL + ". Ensure FastAPI is running.";
    fileObj.statusText = "\u2715 Connection Error";
    updateSingleFileItemDOM(fileObj);
    onDone();
  };

  xhr.send(formData);
}

/* Fast in-place DOM update for individual file card */
function updateSingleFileItemDOM(fileObj) {
  var el = document.querySelector('[data-id="' + fileObj.id + '"]');
  if (!el) return;

  var fill = el.querySelector(".progress-fill");
  var statusSpan = el.querySelector(".file-item-status");
  var metaSpan = el.querySelector(".file-item-meta");

  if (fill) {
    fill.style.width = Math.round(fileObj.progress) + "%";
  }

  if (statusSpan) {
    statusSpan.textContent = fileObj.statusText;
    statusSpan.className = "file-item-status";
    if (fileObj.status === "processed") statusSpan.className += " status-processed";
    else if (fileObj.status === "processing") statusSpan.className += " status-processing";
    else if (fileObj.status === "failed") statusSpan.className += " status-failed";
  }

  if (fileObj.unitsExtracted !== null && metaSpan) {
    metaSpan.innerHTML = escapeHTML(fileObj.type) + " &bull; " + formatFileSize(fileObj.size) + " &bull; " + fileObj.unitsExtracted + " content units";
  }

  if (fileObj.error) {
    var details = el.querySelector(".file-item-details");
    var existingError = details.querySelector(".file-error-text");
    if (!existingError) {
      var errSpan = document.createElement("span");
      errSpan.className = "file-error-text";
      errSpan.textContent = fileObj.error;
      details.appendChild(errSpan);
    } else {
      existingError.textContent = fileObj.error;
    }
    el.classList.add("file-item-error");
  }
}

function onUploadBatchComplete() {
  // After a brief pause, remove successfully processed files from selected list
  // and update the uploaded materials list
  setTimeout(function () {
    selectedFiles = selectedFiles.filter(function (f) {
      return f.status !== "processed";
    });
    renderSelectedFiles();
    updateUploadButton();
    renderUploadedMaterials();
  }, 1000);
}

/* =============================================
   LOCAL STORAGE PERSISTENCE
   ============================================= */

function saveMaterialMetadata(newMaterial) {
  var existing = JSON.parse(localStorage.getItem(MATERIALS_KEY)) || [];
  // Prevent duplicate storage of same fileId
  var alreadyExists = existing.some(function (m) {
    return m.fileId === newMaterial.fileId;
  });

  if (!alreadyExists) {
    existing.push(newMaterial);
    localStorage.setItem(MATERIALS_KEY, JSON.stringify(existing));
  }
}

/* =============================================
   UPLOADED MATERIALS LIBRARY
   ============================================= */

function renderUploadedMaterials() {
  var raw = localStorage.getItem(MATERIALS_KEY);
  var materials = raw ? JSON.parse(raw) : [];
  var section = document.getElementById("uploadedSection");
  var container = document.getElementById("uploadedList");

  if (materials.length === 0) {
    section.style.display = "none";
    container.innerHTML = "";
    return;
  }
  section.style.display = "block";

  var html = "";

  materials.forEach(function (m) {
    var icon = getFileIcon(m.extension);
    var sizeStr = formatFileSize(m.size);

    html += '<div class="file-item" data-id="' + m.id + '">';
    html += '  <div class="file-item-row">';
    html += '    <span class="file-item-icon">' + icon + "</span>";
    html += '    <div class="file-item-details">';
    html += '      <span class="file-item-name">' + escapeHTML(m.name) + "</span>";
    html += '      <span class="file-item-meta">' + escapeHTML(m.type) + " &bull; " + sizeStr;
    if (m.unitsExtracted) {
      html += " &bull; " + m.unitsExtracted + " units extracted";
    }
    html += "      </span>";
    html += "    </div>";
    html += '    <span class="file-item-status status-processed">\u2713 Processed</span>';
    html += '    <button class="btn-delete" data-id="' + m.id + '" title="Delete">\uD83D\uDDD1\uFE0F</button>';
    html += "  </div>";
    html += "</div>";
  });

  container.innerHTML = html;

  // Attach delete button listeners
  container.querySelectorAll(".btn-delete").forEach(function (btn) {
    btn.addEventListener("click", function () {
      deleteMaterial(btn.getAttribute("data-id"));
    });
  });
}

function deleteMaterial(id) {
  var raw = localStorage.getItem(MATERIALS_KEY);
  var materials = raw ? JSON.parse(raw) : [];

  materials = materials.filter(function (m) {
    return m.id !== id;
  });

  localStorage.setItem(MATERIALS_KEY, JSON.stringify(materials));
  renderUploadedMaterials();
}

/* =============================================
   UTILITY HELPERS
   ============================================= */

function generateId() {
  return "mat_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
}

function getExtension(filename) {
  var idx = filename.lastIndexOf(".");
  return idx === -1 ? "" : filename.substring(idx).toLowerCase();
}

function getTypeLabel(ext) {
  switch (ext) {
    case ".pdf":  return "PDF";
    case ".ppt":  return "PPT";
    case ".pptx": return "PPTX";
    case ".mp4":  return "Video";
    default:      return "File";
  }
}

function getFileIcon(ext) {
  switch (ext) {
    case ".pdf":  return "\uD83D\uDCD5"; // 📕
    case ".ppt":
    case ".pptx": return "\uD83D\uDCCA"; // 📊
    case ".mp4":  return "\uD83C\uDFA5"; // 🎥
    default:      return "\uD83D\uDCC4"; // 📄
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

function escapeHTML(str) {
  if (!str) return "";
  var div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
