# VIDYA-X AI — AI Trust & Safety Audit

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Step:** 18 — Trust, Safety, Privacy & Responsible AI Engineering  
**Audit Date:** 2026-10-13  
**Auditor:** Senior AI Safety & Application Security Engineer  

> This audit is based on direct inspection of the actual repository code. Every finding references specific files and line numbers.

---

## 1. Threat Model Summary

| Threat Actor | Goal | Primary Attack Surface |
|---|---|---|
| **Adversarial student** | Extract other students' data, manipulate mastery scores | API endpoints that accept `student_id` or `course_id` from the browser |
| **Malicious course uploader** | Inject instructions into LLM via document content | PDF/PPTX text extraction → tutor prompt context |
| **Passive eavesdropper** | Intercept API keys or private course content | Network, logs, error responses |
| **Buggy LLM response** | Crash service, insert XSS into browser, expose internal paths | Structured JSON validation, HTML rendering |
| **DoS attacker** | Exhaust API quota or crash server | Unbounded retries, large file uploads |

---

## 2. Risk Inventory

| # | Risk | File / Endpoint | Impact | Mitigation | Status |
|:---:|---|---|---|---|:---:|
| R-01 | **No server-side authorization** — `student_id` and `course_id` are accepted from client without verification | All `/api/learner/*`, `/api/quiz/*`, `/api/study-plan/*` | Any client can read or modify any student's data | Add middleware auth; document as demo-mode limitation | ⚠️ Documented; Demo-mode only |
| R-02 | **Prompt injection via uploaded documents** — Retrieved source text is inserted directly into LLM prompts | `services/tutor_service.py:114`, `services/misconception_detection_service.py` | Malicious PDF content could attempt to override system instructions | `SOURCE [N] (file, loc):` delimiter wraps evidence; system instruction enforced | ✅ Partial defense in place |
| R-03 | **Model-invented citations** — LLM could emit `[1]` for chunks it fabricated | `services/tutor_service.py:100–112` | Student shown citation to non-existent page | Citations are built from DB-retrieved chunk metadata before prompt, not from LLM output | ✅ Server-side citation construction |
| R-04 | **False abstention / false grounding** — Threshold mis-calibration | `services/tutor_service.py:17,62` | Correct answers refused; wrong answers accepted | Dual check: vector similarity ≥ 0.15 AND lexical keyword overlap | ✅ Implemented; threshold needs tuning |
| R-05 | **LLM hallucination in quizzes** — Generated question has wrong answer key | `services/question_verification_service.py` | Students graded against wrong answers | Structural validation + source_ref chunk ID verification | ✅ Implemented |
| R-06 | **Answer key exposed pre-submission** — `include_answers=False` not enforced everywhere | `services/quiz_service.py:94–100` | Students can inspect answer before answering | `get_quiz()` always calls `_serialize_session(include_answers=False)` | ✅ Implemented |
| R-07 | **Numerical grading strips signs** — Regex `[^\d\.\-\+eE]` for numeric parsing | `services/quiz_service.py:293` | `-9.8` and `9.8` would both parse to `9.8` | Negative sign is included in the character class (`\-`) | ✅ Sign preserved |
| R-08 | **Misconception from single ambiguous error** — High LLM confidence on 1 attempt | `services/misconception_service.py:264` | Student wrongly labeled with misconception | Deterministic checks first; status starts `suspected`; only escalates to `supported` at ≥2 occurrences or ≥0.70 confidence | ✅ Implemented |
| R-09 | **Path traversal in file uploads** — Attacker uploads `../../etc/passwd` | `services/file_service.py:29–42` | Server-side file overwrite or read | `sanitize_filename()` strips `..`, null bytes, and non-safe chars; uses generated `file_id` prefix | ✅ Implemented |
| R-10 | **Stack traces in API error responses** | `backend/main.py` exception handlers | Leaks internal paths, library versions, SQL structure | Generic error messages returned; details logged server-side only | ✅ Implemented |
| R-11 | **API key in logs or responses** | `services/llm_service.py`, `backend/main.py` | API key exposure | `/health/ai` reports availability without leaking key; keys only in env vars | ✅ Implemented |
| R-12 | **Unbounded LLM retries** | `services/question_generation_service.py`, `services/tutor_service.py` | API quota exhaustion, denial of service | Tutor has single-call + deterministic fallback; question gen has bounded retry | ✅ Partial |
| R-13 | **XSS via LLM-generated Markdown** | Frontend `tutor.html`, `remediation.html` | JavaScript injection in browser | **Gap**: content rendered via `innerHTML` in some pages — needs `textContent` audit | ❌ Gap identified |
| R-14 | **Course isolation in visual assets** | `services/visual_retrieval_service.py` | Visual from Course A shown to Course B student | `get_visual_asset_detail()` enforces `course_id` filter | ✅ Implemented |
| R-15 | **FFmpeg shell injection** — If filename included in shell command | `processors/video_processor.py` | Remote code execution | Subprocess called with list args (not shell string interpolation) | ✅ Verify confirmed |
| R-16 | **Mastery presented as exam probability** | API responses, frontend `progress.html` | Student over/under-confident | `overall_mastery=None` for no-history students; `has_history` flag returned | ⚠️ Needs UI disclaimer |
| R-17 | **Structured LLM JSON parsed without validation** | `services/vision_service.py:_parse_vision_response` | Malformed JSON crashes service | `_parse_vision_response` catches `JSONDecodeError`; sets `uncertain_regions` | ✅ Implemented |
| R-18 | **Demo reset beyond isolation scope** | `POST /api/demo/reset` | Attacker deletes all student data | Reset scoped strictly to `course_demo_physics` and `student_demo` | ✅ Implemented |
| R-19 | **CORS wildcard in development** | `backend/main.py:72`, `backend/config.py` | Cross-origin API calls in production | Production uses `FRONTEND_ORIGINS` env var; dev falls back to `["*"]` | ✅ Configurable |
| R-20 | **No rate limiting on expensive AI endpoints** | `/api/tutor/ask`, `/api/quiz/generate` | Per-request LLM cost and quota exhaustion | No rate limiting implemented | ❌ Gap |

---

## 3. Area-by-Area Analysis

### 3.1 Retrieval & Grounding

**Implemented correctly:**
- `semantic_search()` always applies `WHERE course_id = :course_id` isolation.
- Empty retrieval (`chunks = []`) triggers safe abstention before any LLM call.
- Top-score + lexical overlap dual-gate prevents near-miss false positives.

**Gaps:**
- No maximum context size enforcement before prompt assembly (`context_text` could be extremely large if `top_k` is large).
- Retrieval score ≥ threshold does not guarantee factual correctness — this is correctly NOT claimed in the codebase.

### 3.2 Citation Integrity

**Implemented correctly:**
- Citations are constructed entirely from DB-retrieved chunk metadata (file_name, page, slide, timestamp) — never from LLM output.
- `ref_key` deduplication prevents duplicate citation entries.
- `chunk_id` is included in each citation for traceability.

**Gaps:**
- No post-generation validation that LLM citation brackets `[1]`, `[2]` in response text actually reference chunks that were provided.
- Revision and flashcard services use a `source_ref_ids` list but do not re-verify each ID exists before returning to client.

### 3.3 Prompt Injection Defense

**Implemented (partial):**
- Retrieved passages are wrapped as `SOURCE [N] (file, loc):\n{content}` before insertion into prompts.
- System instruction `"Your answers must be grounded STRICTLY in the provided course excerpts"` precedes user content.

**Gaps:**
- A sufficiently adversarial document could attempt to close the `SOURCE [N]` delimiter and inject new instructions. This is a known limitation of prompt-level injection defense.
- The system relies on the LLM to respect its system instruction — a defense-in-depth approach (input sanitization, output validation) is recommended additionally.

### 3.4 Quiz Validation

**Implemented correctly:**
- `verify_question()` checks required fields, question type whitelist, MCQ 4-option structure, correct_answer in option keys, non-empty option text, source_ref DB existence, prompt length bounds.
- `filter_verified()` removes defective candidates before storage.
- SHA-256 deduplication fingerprinting prevents duplicate questions.

**Gaps:**
- Duplicate MCQ option text (two options with the same text but different keys) is not checked.
- MCQ with multiple keys matching `correct_answer` is possible if answer key is set to a letter appearing in option text.

### 3.5 Grading Transparency

**Implemented correctly:**
- MCQ grading: exact case-insensitive key comparison.
- Numerical: tolerant float comparison with 1% relative tolerance; preserves negative signs.
- Short-answer: keyword overlap ratio with partial credit.
- Answer key never returned in `get_quiz()` (pre-submission); only returned in `submit_answer()` response.

**Known limitations (documented):**
- Short-answer keyword matching is a proxy for semantic correctness; a correct paraphrase using different vocabulary may score low.
- Numerical tolerance is 1% relative — not configurable per-question; questions requiring exact integer answers may need zero tolerance.
- No unit-aware dimensional analysis.

### 3.6 Misconception Detection

**Implemented correctly:**
- Deterministic checks run first (sign error, unit conversion, missing units, scale error, MCQ distractor pattern).
- LLM analysis only runs when deterministic checks find nothing.
- Status machine: `suspected` → `supported` (at ≥2 occurrences) → `improving` (on correct answer) → `resolved`.
- `calculate_misconception_confidence()` caps at 0.95.
- `_update_misconceptions_on_correct_attempt()` moves active records to `improving`/`resolved` on success.

**Gaps:**
- LLM misconception analysis uses student answer verbatim in the prompt — potential privacy consideration.
- No cooldown on misconception escalation; rapid repeated incorrect answers in the same session escalate immediately.

### 3.7 Data Protection & Authorization

**Critical gap (R-01):**  
VIDYA-X AI has **no server-side authentication or authorization layer**. All protected records are retrieved using `student_id` and `course_id` values that come directly from the browser. Any user who knows (or guesses) another student's ID can read their mastery records, quiz attempts, and misconception data.

**This is explicitly documented as a demo-mode limitation.** The application is not suitable for production with real student data in this state.

**Implemented data isolation:**
- All DB queries include both `student_id` and `course_id` as filter parameters.
- Cross-course access is blocked by `course_id` filter in every query.
- Demo reset is strictly scoped to `course_demo_physics`/`student_demo`.

### 3.8 File Processing Security

**Implemented correctly:**
- `sanitize_filename()` strips `..`, null bytes, non-safe chars.
- Files stored as `{file_id}_{sanitized_name}` — no user-controlled path component.
- Upload size limited to 50MB (configurable via `MAX_UPLOAD_SIZE_MB`).
- Extension whitelist: `.pdf`, `.ppt`, `.pptx`, `.mp4` only.

**Gaps:**
- No processing time limit for video transcription (CPU whisper on long videos can exceed request timeout).
- Visual assets are stored with server-side paths that are never returned to the client (correct), but there is no signed URL or access token on asset serving endpoints.

---

## 4. Priority Ranking of Remaining Gaps

| Priority | Risk | Impact | Effort |
|:---:|---|---|---|
| **P1** | R-01: No server-side auth | Critical for any real deployment | High (requires auth system) |
| **P2** | R-13: Potential XSS via innerHTML on generated content | High for security | Low (textContent audit) |
| **P3** | R-20: No rate limiting on LLM endpoints | Medium-High (cost/quota) | Medium (add middleware) |
| **P4** | R-12: Unbounded question generation retries | Medium | Low (add MAX_RETRIES) |
| **P5** | R-16: Mastery UI needs disclaimer | Low-Medium | Low (UI label) |
| **P6** | Post-generation citation bracket validation | Low-Medium | Medium |
| **P7** | Configurable numerical tolerance per question | Low | Medium |

---

## 5. Tests Performed

All 65 automated pytest tests pass (see `backend/test_*.py`). Safety-specific tests added in `backend/test_trust_safety.py` (Step 18) cover:
- Prompt injection via adversarial document content
- Unsupported query abstention
- MCQ option validation edge cases
- Numerical grading sign preservation
- File sanitization edge cases
- Missing answer key rejection
- Duplicate MCQ option detection
