# VIDYA-X AI

> **Your Personal AI Study Companion** — An AI-powered personalized tutoring, adaptive practice, and misconception remediation platform.

VIDYA-X AI delivers a personalized study experience by combining multimodal course-material processing, knowledge structuring, adaptive quizzes, Bayesian Knowledge Tracing (BKT) learner modeling, adaptive question selection, AI tutoring, and misconception detection with personalized remediation — all grounded in the student's actual study materials.

---

## Multimodal Adaptive & Remediation Loop

```text
Student Response
   ↓
Automated Evaluation (MCQ, Short-Answer, Numerical)
   ↓
BKT Learner Model Update (Prior → Posterior Mastery)
   ↓
Fast Deterministic Error Checks (Sign, Scale, Units, Arithmetic)
   ↓ (If Ambiguous)
Grounded LLM Diagnostic Analysis (Course RAG Chunks)
   ↓
Misconception Detection & Evidence Logging (Suspected / Supported)
   ↓
Personalized Remediation Session (remediation.html)
   ├─ Grounded Corrective Explanation & Citations
   ├─ Mistake vs Correct Concept Contrast Card
   ├─ Step-by-Step Worked Example
   ├─ Interactive Self-Check Question
   └─ Targeted Practice Questions
   ↓
Activity Completion & Cautious Post-Remediation Outcome Evaluation
```

---

## Current Status: Step 15 — Final Integration, Product Polish & Hackathon Demo ✅ — Multimodal Course Understanding & Visual Intelligence Engine ✅ — Evaluation, Benchmarking & Quality Assurance Framework ✅ — Intelligent Study Planner & Spaced Repetition Engine ✅

> **Key Principle**: Step 8 answered *"What does this student know?"*, Step 9 answered *"What should this student practice next?"*, Step 10 answered *"What recurring misunderstanding is causing errors?"*, Step 11 answered *"How can this student efficiently consolidate course knowledge?"*, and Step 12 answers *"How should the student structure their available study time today and this week to achieve maximum exam readiness?"*.

### Completed Steps:

#### Step 1 — Student & Course Setup ✅
- Student profile creation (name, course, language, exam date, daily study time).
- Client-side validation and browser `localStorage` persistence under `vidyaXProfile`.
- Dynamic dashboard displaying personalized welcome and course metrics.

#### Step 2 — Multimodal Upload UI ✅
- Drag-and-drop and file-browser selection for PDF, PPT, PPTX, and MP4.
- Client-side format & size checks (max 500 MB per file).
- Uploaded material library with deletion and live dashboard counter.

#### Step 3 — Multimodal Content Extraction Backend ✅
- **FastAPI backend** with CORS enabled.
- **PyMuPDF PDF Processor**: Page-by-page extraction with 1-based page index.
- **python-pptx Processor**: Slide-by-slide text and speaker notes extraction.
- **faster-whisper Video Processor**: FFmpeg audio extraction and timestamped transcription (`HH:MM:SS`).

#### Step 5 — Knowledge Base & Vector Search ✅
- Structured knowledge extraction (Topics, Concepts, Definitions, Relationships).
- `pgvector` semantic retrieval with course-isolated cosine similarity.

#### Step 7 — Adaptive Question & Quiz Engine ✅
- Grounded question generation (MCQ, short-answer, numerical) exclusively from course material.
- SHA-256 fingerprinting for question deduplication.
- Quiz sessions, attempt storage, evaluation, and feedback with exact citations.

#### Step 8 — Learner Model & BKT Engine ✅
- **Pure BKT Service** (`bkt_service.py`):
  - Bayesian update formula for correct/incorrect answers.
  - Continuous evidence update (`update_bkt_with_evidence`) for short-answer partial credit.
  - Configurable parameters (`P(L0)=0.20`, `P(T)=0.10`, `P(G)=0.20`, `P(S)=0.10`).
  - Clamping enforced: `0.0 <= mastery <= 1.0`.
- **Learner Model Service** (`learner_model_service.py`):
  - Bridges quiz answer submission → BKT updates.
  - Dual-level granularity: `LearnerTopicMastery` and `LearnerConceptMastery`.

#### Step 9 — Adaptive Question Selection Engine ✅
- **Candidate Question Retrieval & Recency Filtering** (`candidate_service.py`).
- **Transparent Weighted Scoring Model** (`adaptive_scoring_service.py`):
  - Mastery weakness, difficulty fit, recent failure, prerequisite boost, novelty, and diversity.
- **Real-Time Adaptation**: Dynamic next question selection (`GET /api/adaptive/next-question`).

#### Step 10 — Misconception Detection & Personalized Remediation ✅
- **12 Standard Error Categories**:
  - `conceptual_misunderstanding`, `formula_selection_error`, `formula_substitution_error`, `arithmetic_calculation_error`, `unit_conversion_error`, `missing_incorrect_units`, `sign_direction_error`, `definition_confusion`, `misinterpretation_question`, `incomplete_explanation`, `careless_error`, `unknown_insufficient_evidence`.
- **Deterministic-First Diagnostic Pipeline**:
  - Fast rule-based checks for sign errors, unit conversion factors (1000x, 100x, 60x), missing units, and minor arithmetic deviations before LLM calls.
- **Grounded LLM Analysis with Source Citations**:
  - Constrained Gemini analysis with JSON schema validation and mapping to retrieved RAG chunks (`SOURCE_N`).
- **Idempotent Evidence & Status Lifecycle**:
  - Unique DB constraint on `(misconception_id, attempt_id)`.
  - State machine transitions: `suspected` (1 attempt) → `supported` (2+ attempts or high confidence) → `under_review` (remediation created) → `improving` (correct attempt) → `resolved` (sustained correctness).
- **Grounded Remediation Sessions & Dedicated UI (`remediation.html`)**:
  - Corrective explanations in preferred language (English, Hindi, Hinglish).
  - Mistake vs Correct approach contrast cards.
  - Step-by-step worked examples.
  - Self-check interactive questions.
  - Targeted practice questions.

#### Step 11 — Personalized Revision Materials & Flashcard Engine ✅
- **8 Grounded Material Types**: `topic_summary`, `revision_notes`, `exam_revision_sheet`, `formula_sheet`, `concept_comparison`, `definitions_terminology`, `quick_checklist`, `weak_topic_study_guide`.
- **Mastery & Misconception Personalization**: Prioritizes weak topics (BKT < 0.50) and active misconceptions while honoring student topic selections.
- **Grounded Source Citation Resolution**: Every material section, comparison matrix row, and self-check question links to exact course chunks (`file_name`, `page`, `slide`, `timestamp`). Rejects ungrounded LLM citations.
- **Interactive Flashcards Engine**: Active recall decks with 3D flip card animations, difficulty distribution (`easy`, `medium`, `hard`), active misconception emphasis, SHA-256 card fingerprint deduplication, and spaced review ratings (`again`, `hard`, `good`, `easy`).

#### Step 12 — Intelligent Study Planner & Spaced Repetition Engine ✅
- **Deterministic 6-Signal Topic Prioritization**: Weighted signals for BKT mastery need (30%), recent errors (20%), active supported misconceptions (15%), prerequisite dependencies (15%), due flashcard queue (10%), and exam proximity (10%).
- **Spaced Repetition Scheduler**: Configurable active recall interval algorithm (`again` -> 10m, `hard` -> 1.0d, `good` -> 3.0d, `easy` -> 7.0d) with card scheduling state persistence.
- **Adaptive Daily & Weekly Schedules (`study-plan.html`)**: Generates 7-day or 14-day study plans respecting daily study time budget, exam date boundaries, unavailable dates, and session durations.
- **Task Lifecycle & Completion Tracking**: Supports task states (`pending`, `in_progress`, `completed`, `skipped`, `rescheduled`, `cancelled`) with completion time tracking and rescheduling.
- **Empirical Exam Readiness Tracker (`exam-readiness.html`)**: Evaluates student readiness into evidence-based categories (`insufficient_data`, `needs_substantial_review`, `building_readiness`, `reasonably_prepared`) with confidence indicators and actionable next steps.

---

## File Structure

```text
VIDYA-X-AI/
├── frontend/
│   ├── index.html              ← "Create Your Study Profile" page
│   ├── css/
│   │   ├── style.css           ← Global styles
│   │   ├── upload.css          ← Upload page styles
│   │   ├── quiz.css            ← Quiz engine & adaptive styles
│   │   ├── progress.css        ← Learner progress styles
│   │   ├── remediation.css     ← Remediation session styles (Step 10)
│   │   ├── revision.css        ← Revision Studio styles (Step 11)
│   │   ├── flashcards.css      ← Flashcards Studio styles (Step 11)
│   │   ├── study-plan.css      ← Smart Study Planner styles (Step 12)
│   │   └── exam-readiness.css  ← Exam Readiness styles (Step 12)
│   ├── js/
│   │   ├── app.js              ← Profile, dashboard & quick nav counters
│   │   ├── upload.js           ← Upload logic
│   │   ├── quiz.js             ← Adaptive quiz flow & misconception callout
│   │   ├── progress.js         ← Learner progress logic
│   │   ├── remediation.js      ← Remediation session handler (Step 10)
│   │   ├── revision.js         ← Revision material generator & renderer (Step 11)
│   │   ├── flashcards.js       ← Active recall 3D flashcard study engine (Step 11)
│   │   ├── study-plan.js       ← Smart Study Planner schedule handler (Step 12)
│   │   └── exam-readiness.js   ← Exam Readiness evaluation renderer (Step 12)
│   └── pages/
│       ├── dashboard.html      ← Student dashboard with Planner & Readiness cards
│       ├── upload.html         ← Course material upload
│       ├── quiz.html           ← Practice & Adaptive Quiz page
│       ├── progress.html       ← Learning progress dashboard
│       ├── remediation.html    ← Dedicated Remediation page (Step 10)
│       ├── revision.html       ← Revision Studio page (Step 11)
│       ├── flashcards.html     ← Flashcards Studio page (Step 11)
│       ├── study-plan.html     ← Smart Study Planner page (Step 12)
│       └── exam-readiness.html ← Exam Readiness Tracker page (Step 12)
│
├── backend/
│   ├── main.py                         ← FastAPI application & endpoints (v1.2.0)
│   ├── requirements.txt                ← Python dependencies
│   ├── test_study_plan.py              ← Step 12 test suite (12/12 passing)
│   ├── test_revision.py                ← Step 11 test suite (10/10 passing)
│   ├── test_misconception.py           ← Step 10 test suite (8/8 passing)
│   ├── test_adaptive.py                ← Step 9 test suite (8/8 passing)
│   ├── test_bkt.py                     ← Step 8 test suite (26/26 passing)
│   ├── test_quiz.py                    ← Step 7 test suite (13/13 passing)
│   ├── database/
│   │   ├── connection.py               ← SQLAlchemy engine & SQLite fallback
│   │   └── models.py                   ← ORM models (including StudyPlan, StudyPlanDay, StudyPlanTask, StudentStudyPreferences)
│   └── services/
│       ├── spaced_repetition_service.py← Spaced repetition interval calculator (Step 12)
│       ├── prioritization_service.py   ← 6-signal topic prioritization engine (Step 12)
│       ├── study_planner_service.py    ← Daily & weekly study plan generator (Step 12)
│       ├── study_plan_tracking_service.py ← Task lifecycle & completion tracker (Step 12)
│       ├── exam_readiness_service.py   ← Empirical exam readiness evaluator (Step 12)
│       ├── revision_personalization_service.py ← Personalization plan from BKT & misconceptions (Step 11)
│       ├── revision_validation_service.py      ← Topic validation & citation mapping (Step 11)
│       ├── revision_generation_service.py      ← Grounded study material generator (Step 11)
│       ├── flashcard_service.py               ← Flashcard deck generator & review tracker (Step 11)
│       ├── revision_service.py                ← Revision & flashcards orchestrator (Step 11)
│       ├── misconception_detection_service.py ← Deterministic & LLM diagnostics (Step 10)
│       ├── misconception_service.py           ← Misconception state machine (Step 10)
│       ├── remediation_service.py             ← Grounded remediation generator (Step 10)
│       ├── candidate_service.py               ← Candidate question retrieval (Step 9)
│       ├── adaptive_scoring_service.py        ← Candidate scoring (Step 9)
│       ├── adaptive_service.py                ← Adaptive orchestration (Step 9)
│       ├── bkt_service.py                     ← Pure BKT math (Step 8)
│       ├── learner_model_service.py           ← BKT attempt integration (Step 8)
│       └── quiz_service.py                    ← Quiz session manager (Step 7)
│
└── README.md
```

---

## Backend Setup & Running

### 1. Run All Tests
```bash
python backend/test_study_plan.py   # Step 12 test suite (12/12 passed)
python backend/test_revision.py     # Step 11 test suite (10/10 passed)
python backend/test_misconception.py  # Step 10 test suite (8/8 passed)
python backend/test_adaptive.py       # Step 9 test suite (8/8 passed)
python backend/test_bkt.py            # Step 8 test suite (26/26 passed)
python backend/test_quiz.py           # Step 7 test suite (13/13 passed)
```

### 2. Run the Server
```bash
uvicorn backend.main:app --reload
```
- **Base URL**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`

---

## Key API Endpoints (Step 12 Added)

### Smart Study Planner & Spaced Repetition
- `POST /api/study-plan/generate`: Generate a personalized 7- or 14-day study plan.
- `GET /api/learner/{student_id}/course/{course_id}/study-plan`: Retrieve active study plan.
- `GET /api/study-plan/{plan_id}`: Retrieve specific study plan details.
- `GET /api/learner/{student_id}/course/{course_id}/study-plan/today`: Retrieve today's scheduled tasks.
- `PATCH /api/study-plan/tasks/{task_id}`: Update task status or reschedule task.
- `POST /api/study-plan/tasks/{task_id}/complete`: Record task completion with actual study minutes.
- `GET /api/learner/{student_id}/course/{course_id}/reviews/due`: Retrieve due spaced repetition flashcard queue.
- `GET /api/learner/{student_id}/course/{course_id}/exam-readiness`: Retrieve empirical exam readiness analysis.
- `PATCH /api/learner/{student_id}/course/{course_id}/study-preferences`: Update study budget, exam date, or selected topics.

---

## Roadmap

| Step | Feature | Status |
|:---:|:---|:---:|
| 1 | Student & Course Setup (HTML / CSS / JS / localStorage) | ✅ Completed |
| 2 | Multimodal Upload UI & Material Management | ✅ Completed |
| 3 | Multimodal Extraction Backend (PyMuPDF, python-pptx, faster-whisper) | ✅ Completed |
| 5 | Knowledge Base & Vector Search (pgvector, semantic retrieval) | ✅ Completed |
| 7 | Adaptive Question & Quiz Engine (MCQ, short-answer, numerical, deduplication) | ✅ Completed |
| 8 | Learner Model, Topic Mastery & BKT Engine | ✅ Completed |
| 9 | Adaptive Question Selection & Personalized Practice | ✅ Completed |
| 10 | Misconception Detection & Personalized Remediation | ✅ Completed |
| 11 | Personalized Revision Materials & Flashcard Engine | ✅ Completed |
| 12 | Intelligent Study Planner & Spaced Repetition Engine | ✅ Completed |
| 13 | Evaluation, Benchmarking & Quality Assurance Framework | ✅ Completed |
| 14 | Multimodal Course Understanding & Visual Intelligence Engine | ✅ Completed |
| 15 | Final Integration, Product Polish & Hackathon Demo | ✅ Completed |
| 16 | Deployment, Production Readiness & Live Launch (Docker, Health Probes, Production Config) | ✅ Completed |
| 17 | Hackathon Pitch, Architecture, Evaluation & Judge Preparation | ✅ Completed |

---

## Production Deployment & Operations (Step 16 Added)

VIDYA-X AI includes full production readiness tooling:
- **Health Probes**: Liveness (`/health`), Readiness (`/health/ready`), and AI diagnostics (`/health/ai`).
- **Containerization**: Multi-stage `Dockerfile` (Python 3.12-slim, non-root `appuser`, FFmpeg, libpq) and `docker-compose.yml` (PostgreSQL with `pgvector`, FastAPI backend, and Nginx reverse proxy).
- **Automated Verification**: End-to-end smoke test suite in `scripts/smoke_test.py`.
- **Database Initialization**: Idempotent table and vector extension setup script `scripts/init_db.py`.
- **Comprehensive Documentation**: Full deployment guides in [`docs/deployment_guide.md`](docs/deployment_guide.md) and [`docs/deployment_readiness_audit.md`](docs/deployment_readiness_audit.md).

---

## Hackathon Pitch, Architecture & Judge Materials (Step 17 Added)

- **Pitch Deck & Scripts**: [`docs/hackathon_pitch.md`](docs/hackathon_pitch.md) (30s, 90s, and complete 6-minute slide-by-slide spoken script).
- **Presentation Slides**: [`presentation/VIDYA_X_AI_Hackathon_Pitch.pptx`](presentation/VIDYA_X_AI_Hackathon_Pitch.pptx).
- **System Architecture & Data Flow**: [`docs/system_architecture.md`](docs/system_architecture.md) (Full Mermaid flowcharts, components, and trade-offs).
- **Evidence-Based Feature Matrix**: [`docs/feature_verification_matrix.md`](docs/feature_verification_matrix.md) (Honest status across all 25 system capabilities).
- **Evaluation & Benchmarking Report**: [`docs/hackathon_evaluation_summary.md`](docs/hackathon_evaluation_summary.md) (Actual measured results, release gates, and analysis).
- **Reproducible Evaluation Protocol**: [`docs/evaluation_action_plan.md`](docs/evaluation_action_plan.md) (Benchmarking protocol across 6 dimensions).
- **Judge Q&A Guide**: [`docs/judge_qa.md`](docs/judge_qa.md) (38 concise, technically defensible answers across 6 categories).
- **Live Demo Fallback Protocol**: [`docs/demo_fallback_plan.md`](docs/demo_fallback_plan.md) (3-tier contingency plan for Wi-Fi or API hiccups).

## License

Built for learning & hackathon demonstration.


