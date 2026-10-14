# VIDYA-X AI — Privacy & Data Handling Policy

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Step:** 18 — Trust, Safety, Privacy & Responsible AI Engineering  
**Effective Date:** 2026-10-13  

> This document describes what data VIDYA-X AI stores, why, who can access it, and its current limitations. It is intended to be honest and complete, not aspirational.

---

## 1. What Data Is Stored

### 1.1 Student Profile Data
| Data Field | Storage Location | Why Stored | Retention |
|---|---|---|---|
| Student name | Browser `localStorage['vidyaXProfile']` only | Personalizing the UI | Until browser storage is cleared by user |
| Student ID (auto-generated slug) | Browser `localStorage`, URL params, backend DB | Linking mastery and quiz records | Until records are deleted |
| Preferred language | Browser `localStorage` | Localization of tutor responses | Until profile reset |
| Exam date | Browser `localStorage` + `study_plans` DB table | Study plan generation | Until plan is updated |
| Daily study time | Browser `localStorage` + `study_plans` DB table | Task scheduling | Until preferences updated |

### 1.2 Course & Material Data
| Data | Storage Location | Why Stored | Sensitivity |
|---|---|---|---|
| Uploaded PDF/PPTX/MP4 files | `backend/uploads/` (server disk) | Source extraction; citation resolution | Contains student's course IP |
| Extracted text chunks | `knowledge_chunks` DB table | Vector retrieval for grounded answers | Contains excerpts from uploaded materials |
| Vector embeddings | `knowledge_chunks.embedding` column (pgvector) | Semantic search | Mathematical representations of text |
| Visual asset images | `backend/visual_assets/` (server disk) | Citation of diagrams and figures | Contains images from uploaded materials |
| Visual descriptions | `visual_assets.visual_description` column | Searchable visual index | AI-generated text summaries |

### 1.3 Learning & Assessment Data
| Data | Storage Location | Why Stored |
|---|---|---|
| Quiz sessions and questions | `quiz_sessions`, `questions` DB tables | Serving questions and grading |
| Quiz attempts (answer, result, score) | `quiz_attempts` DB table | BKT mastery updates, misconception detection |
| BKT topic mastery probabilities | `learner_topic_mastery` DB table | Adaptive question selection |
| BKT concept mastery probabilities | `learner_concept_mastery` DB table | Personalized recommendations |
| Misconception records | `misconception_records` DB table | Targeted remediation |
| Misconception evidence links | `misconception_evidence` DB table | Confidence tracking across attempts |
| Flashcard decks | `flashcards` DB table | Active recall sessions |
| Flashcard reviews (outcome, timestamp) | `flashcard_reviews` DB table | Spaced repetition scheduling |
| Study plans and tasks | `study_plans`, `study_tasks` DB tables | Daily schedule generation |
| Revision materials | `revision_materials` DB table | Study reference sheets |

---

## 2. What Is Sent to External AI Providers

### 2.1 Gemini API (google-generativeai)
The following content types are sent to Google's Gemini API when `GEMINI_API_KEY` is configured:

| Operation | What Is Sent | Contains Personal Data? |
|---|---|---|
| Knowledge structuring (Step 5) | Extracted text chunks from uploaded documents | No personal data; course content only |
| Tutor answer generation | System instruction + student question + up to 4 course text excerpts | Student question text; course excerpts |
| Misconception analysis | Student incorrect answer + expected answer + course context | Student's specific incorrect answer |
| Remediation generation | Misconception description + course excerpts | Misconception label (not student identity) |
| Revision generation | Topic names + course excerpts | Course content only |
| Vision analysis (Step 14) | Image bytes from extracted visual assets | Course material images |
| Question generation | Topic/concept names + course text excerpts | Course content only |

**What is NOT sent:**
- Student names, email addresses, or real-world identity.
- Raw uploaded files in their entirety (only extracted text excerpts of ≤2,000 characters per request).
- API keys are never included in prompts or sent to the frontend.
- Database credentials are never sent to any external service.

**Important limitation:** Google's data processing terms and model training policies apply to all content sent to the Gemini API. Review [Google's AI Studio Terms of Service](https://ai.google.dev/terms) and [Google Cloud Data Processing Addendum](https://cloud.google.com/terms/data-processing-addendum) for the applicable data retention and usage terms. VIDYA-X AI does not independently control whether Google uses submitted content for model improvement.

### 2.2 Local Fallback Mode
When `EMBEDDING_PROVIDER=local` is set (the default for testing), all embedding and classification operations run fully locally via `services/embedding_service.py`. No content is sent to external services.

---

## 3. Who Can Access Student Data

### Current Authorization Model (Demo Mode)

> ⚠️ **Critical Limitation**: VIDYA-X AI currently has **no server-side authentication or session management**. All protected records are looked up using `student_id` and `course_id` values supplied directly by the browser client. Any party with network access to the backend who knows (or guesses) a `student_id` can read all associated mastery records, quiz attempts, and misconceptions.

This is an **intentional demo-mode design** acceptable for a hackathon showcase. It is **not suitable for production deployment with real student data** without adding an authentication layer.

**Implemented data isolation (what works):**
- Every database query applies both `student_id` and `course_id` as mandatory filters.
- Demo data is strictly scoped to `student_demo` / `course_demo_physics`.
- Cross-course access is blocked at the SQL query level.
- Internal filesystem paths to uploaded files are never returned to the client.

**What does not work:**
- Unauthenticated clients can supply any `student_id` and retrieve that student's data.
- There is no JWT, session token, or OAuth2 mechanism.

---

## 4. Data Retention & Deletion

### Current Retention Behavior
- Uploaded files and extracted content persist on server disk indefinitely (no automatic expiry).
- Database records persist until the database is dropped or records are manually deleted.
- Demo data can be reset via `POST /api/demo/reset`, which deletes records scoped to `student_demo`/`course_demo_physics`.

### Deletion Support
| Feature | Status |
|---|---|
| Delete uploaded material and its chunks | **Not yet implemented** (no dedicated endpoint) |
| Delete a student's quiz attempts | **Not yet implemented** |
| Delete mastery records | `reset_learner_state()` function exists in `mastery_service.py`; no API endpoint exposes it |
| Delete misconception records | **Not yet implemented** |
| Clear entire demo dataset | ✅ Implemented via `POST /api/demo/reset` |
| SQLite/PostgreSQL schema drop | Manual operation only |

**Recommendation:** Before any production deployment, implement a `DELETE /api/learner/{student_id}` endpoint that cascades to remove all associated records and deletes uploaded files from disk.

---

## 5. Logging Policy

### What Is Logged
VIDYA-X AI uses Python's `logging` module (configured at `WARNING` level in production). The following operational details are logged:

| Event | Log Level | What Is Captured | What Is NOT Captured |
|---|---|---|---|
| Upload processing | INFO | File ID, source type, chunk count | Raw file contents |
| Extraction errors | ERROR | File ID, error category | File contents |
| Vector search | DEBUG (dev only) | Query similarity scores | Query text or chunk content |
| LLM call failures | WARNING | Error type, retry count | API key, prompt content |
| Tutor abstention | INFO | course_id, abstention triggered | Student question text |
| Quiz grading | DEBUG (dev only) | Question ID, is_correct | Student answer text |
| Misconception detected | INFO | misconception_code, confidence | Student answer text |
| Demo reset | INFO | Reset scope confirmation | — |

### What Is NOT Logged By Default
- API keys or authorization headers
- Student question text (only abstention event is logged, not the question)
- Student answer text from quiz submissions
- Full course document text
- Student profile details (name, exam date)
- Conversation history

---

## 6. Known Privacy Limitations

1. **No consent mechanism**: Students are not presented with a data collection notice.
2. **No data export**: Students cannot download their own data.
3. **No data minimization enforcement**: Once a student's quiz attempt is stored, all fields including the exact incorrect answer text are retained indefinitely.
4. **External provider data retention**: Content sent to the Gemini API may be subject to Google's retention policies independently of VIDYA-X AI's local deletion.
5. **Local SQLite mode**: In testing mode, the entire database is a single file that may be copied or accessed without record-level access controls.

---

## 7. Recommended Next Steps Before Production Deployment

1. Implement OAuth2 / JWT authentication with server-side session validation.
2. Add `DELETE /api/learner/{student_id}` with cascading cleanup of all records and uploaded files.
3. Implement a data retention policy (e.g., auto-expire records after 12 months of inactivity).
4. Add a consent banner and privacy notice on the student profile setup page.
5. Review Gemini API terms regarding content sent for model improvement; configure opt-out if available.
6. Enable structured audit logging (request ID, user ID hash, action) for compliance monitoring.
