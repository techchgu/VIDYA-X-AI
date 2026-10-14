/* ==========================================================================
   VIDYA-X AI — Centralized API Client & Context Management (Step 15)
   Provides:
     - Configurable API base URL
     - Standardized request wrapper with timeouts and error handling
     - Active learner and course profile context management
     - Unified error formatting and safe JSON parsing
   ========================================================================== */

// Resolve dynamic API base URL:
// 1. Explicit window.VIDYAX_CONFIG.API_BASE_URL (injected via deployment config)
// 2. Same-origin fallback if running on standard web port
// 3. Default localhost:8000 for local dev
const getBaseUrl = () => {
  if (typeof window !== "undefined" && window.VIDYAX_CONFIG && window.VIDYAX_CONFIG.API_BASE_URL) {
    return window.VIDYAX_CONFIG.API_BASE_URL.replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    // If frontend is served by FastAPI or reverse proxy on same host
    return `${window.location.origin}/api`;
  }
  return "http://localhost:8000/api";
};

const API_CONFIG = {
  baseUrl: getBaseUrl(),
  timeoutMs: 15000,
  storageKey: "vidyaXProfile",
  demoModeKey: "vidyaXDemoMode",
};

/**
 * Retrieve current active student and course context.
 * Standardizes course IDs across all client pages.
 */
function getActiveContext() {
  const isDemo = localStorage.getItem(API_CONFIG.demoModeKey) === "true";
  if (isDemo) {
    return {
      studentId: "student_demo",
      studentName: "Demo Student",
      courseId: "course_demo_physics",
      courseName: "Physics: Classical Mechanics & Newton's Laws",
      preferredLanguage: "English",
      isDemo: true,
    };
  }

  try {
    const raw = localStorage.getItem(API_CONFIG.storageKey);
    if (raw) {
      const p = JSON.parse(raw);
      const courseName = p.courseName || "General Course";
      const courseId = p.courseId || `course_${slugify(courseName)}`;
      return {
        studentId: p.studentId || "student_user",
        studentName: p.studentName || "Student",
        courseId: courseId,
        courseName: courseName,
        preferredLanguage: p.preferredLanguage || "English",
        examDate: p.examDate || null,
        isDemo: false,
      };
    }
  } catch (_) {}

  return {
    studentId: "student_user",
    studentName: "Student",
    courseId: "general",
    courseName: "General Course",
    preferredLanguage: "English",
    examDate: null,
    isDemo: false,
  };
}

function slugify(text) {
  return (text || "general")
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[-\s]+/g, "_");
}

/**
 * Universal safe fetch wrapper with timeout and standard JSON error response.
 */
async function apiRequest(endpoint, options = {}) {
  const url = endpoint.startsWith("http") ? endpoint : `${API_CONFIG.baseUrl}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || API_CONFIG.timeoutMs);

  const defaultHeaders = {
    "Accept": "application/json",
  };
  if (options.body && !(options.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
    });
    clearTimeout(timeoutId);

    let data;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = { text };
    }

    if (!response.ok) {
      const errorMsg = data.error || data.detail || `Request failed with status ${response.status}`;
      return { success: false, status: response.status, error: errorMsg, data };
    }

    return { success: true, status: response.status, ...data };
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      return { success: false, error: "Request timed out. Please check if the backend server is running." };
    }
    return { success: false, error: `Connection failed: ${err.message}` };
  }
}

// Global API helper namespace
window.VidyaAPI = {
  config: API_CONFIG,
  getContext: getActiveContext,
  request: apiRequest,

  // High-level API methods
  async getDashboardSummary() {
    const ctx = getActiveContext();
    return apiRequest(`/dashboard/summary?student_id=${encodeURIComponent(ctx.studentId)}&course_id=${encodeURIComponent(ctx.courseId)}`);
  },

  async askTutor(question) {
    const ctx = getActiveContext();
    return apiRequest("/tutor/ask", {
      method: "POST",
      body: JSON.stringify({
        course_id: ctx.courseId,
        student_id: ctx.studentId,
        question: question,
        preferred_language: ctx.preferredLanguage,
      }),
    });
  },

  async enableDemoMode() {
    const res = await apiRequest("/demo/enable", { method: "POST" });
    if (res.success) {
      localStorage.setItem(API_CONFIG.demoModeKey, "true");
    }
    return res;
  },

  async resetDemoMode() {
    const res = await apiRequest("/demo/reset", { method: "POST" });
    if (res.success) {
      localStorage.setItem(API_CONFIG.demoModeKey, "true");
    }
    return res;
  },

  disableDemoMode() {
    localStorage.removeItem(API_CONFIG.demoModeKey);
  },

  isDemoMode() {
    return localStorage.getItem(API_CONFIG.demoModeKey) === "true";
  },
};
