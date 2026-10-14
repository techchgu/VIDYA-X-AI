# VIDYA-X AI — Hackathon Presentation & Live Demo Guide

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Tagline:** "Learn from your material. Get cited answers. Practice intelligently. Improve continuously."

---

## 1. Quick Start & Setup Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- PostgreSQL with `pgvector` extension (or built-in SQLite fallback for lightweight demos/testing)
- Modern web browser (Chrome, Edge, Firefox, Safari)

### Installation
```bash
# 1. Clone & enter repository
cd "vidya - x"

# 2. Install backend dependencies
pip install -r backend/requirements.txt
```

### Environment Configuration
Create `backend/.env` (optional for local deterministic demo):
```ini
DATABASE_URL=sqlite:///./vidya_x.db
EMBEDDING_PROVIDER=local
EMBEDDING_DIMENSION=384
WHISPER_MODEL=base
VISION_MODEL=gemini-1.5-flash
# Optional: GEMINI_API_KEY=your_key_here
```

### Starting the System
1. **Start Backend**:
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **Serve Frontend**:
   ```bash
   # From project root:
   python -m http.server 3000 --directory frontend
   # Open browser at: http://localhost:3000/pages/dashboard.html
   ```

---

## 2. Live Demo Script & 5–7 Minute Presentation Plan

| Timestamp | Phase | Screen / Page | Actions & Speaking Points | Expected Output | Fallback |
|---|---|---|---|---|---|
| **0:00 – 0:45** | **The Problem & Vision** | Landing / Dashboard | • Explain problem: Generic LLMs hallucinate, lack course alignment, and don't track what a student actually knows.<br>• Introduce VIDYA-X AI: Closes the entire learning loop from uploaded syllabus to adaptive mastery. | Dashboard loads with clean profile context & unified navigation. | Show offline profile state in `localStorage`. |
| **0:45 – 1:45** | **1-Click Demo Mode & Course Materials** | Dashboard & Materials | • Click **⚡ Demo Mode** in the header.<br>• Loads Classical Mechanics course (Newton's Laws, Force, Mass, Friction).<br>• Point out distinction between raw upload and verified structured knowledge chunks. | Header pill turns to *"Physics: Classical Mechanics & Newton's Laws"*; material card shows 4 chunks indexed. | Use `/api/demo/enable` directly via Swagger at `/docs`. |
| **1:45 – 2:45** | **Grounded AI Tutor & Citations** | `tutor.html` | • Ask: *"What is Newton's Second Law relating force and acceleration?"*<br>• Show grounded answer with `[1]` citation pill.<br>• Click citation pill to highlight verified excerpt in sidebar.<br>• **Abstention Demo:** Ask: *"What is the chemical mechanism of photosynthesis in plants?"* | Verified citation to `Newton_Laws_of_Motion_Lecture_Notes.pdf`, Page 2.<br>For biology query: System safely abstains ("I couldn't find sufficient information in your course materials"). | Use preset prompt chips. |
| **2:45 – 3:45** | **Adaptive Practice & BKT Mastery** | `quiz.html` & `progress.html` | • Select **Adaptive Quiz** mode.<br>• Answer questions; engine dynamically adjusts difficulty based on BKT probability.<br>• Navigate to **Progress**: View BKT topic mastery updating in real time. | Quiz grading reveals exact course sources.<br>Mastery tracks Weak (Friction 0.35) vs Mastered topics. | View pre-seeded mastery curves. |
| **3:45 – 4:30** | **Misconception Detection & Remediation** | `remediation.html` | • Show active misconception: *"Assuming Normal Force Always Equals mg on Inclines"*.<br>• Show targeted remediation session with worked example, contrast table, and self-check. | Grounded corrective explanation with prerequisite guidance. | Click directly from Dashboard "Needs Attention" card. |
| **4:30 – 5:15** | **Flashcards & Smart Study Planner** | `flashcards.html` & `study-plan.html` | • Demonstrate 3D active recall flashcard flip.<br>• Rate retention (Easy / Good / Hard) to schedule next review via spaced repetition.<br>• Inspect daily study tasks prioritized by exam boundary. | Spaced repetition intervals calculated; today's task checklist displays. | View 7-day schedule view. |
| **5:15 – 6:00** | **Visual Intelligence Studio** | `visuals.html` | • Explore extracted diagrams, charts, and video frames.<br>• Search: *"circuit diagram"* or filter by visual type (Diagrams, Equations).<br>• Inspect structured metadata and labels. | Visual cards with similarity match % and source page tags. | Click any visual card to open detail drawer. |
| **6:00 – 6:45** | **Technical Credibility & Evaluation** | `evaluation.html` | • Show reproducible benchmark suite.<br>• Explain automated quality gates (Recall@K, MRR, nDCG, Grounding Abstention rate, BKT sanity). | Evaluation dashboard with passed quality release gates. | Re-run runner via `python -m unittest backend/test_evaluation.py`. |
| **6:45 – 7:00** | **Impact & Conclusion** | Dashboard | • Emphasize tagline: *"Learn from your material. Get cited answers. Practice intelligently. Improve continuously."* | Revisit dashboard showing updated progress indicators. | Q&A session. |

---

## 3. Demo Mode Resetting & Isolation Guarantees

- **Activation**: Click **"⚡ Demo Mode"** in the navigation bar on any page.
- **Reset**: Click **"Reset Demo Data"** in the top yellow banner.
- **Isolation Guarantee**: The reset routine strictly filters by `course_id == "course_demo_physics"` and `student_id == "student_demo"`. Real student materials, custom courses, and user quiz attempts are never touched.

---

## 4. Running Automated Tests & Evaluation Suite

```bash
# Run full regression test suite (64 unit/integration tests)
python -m pytest backend/ -v

# Run evaluation & benchmark runner directly
python -m unittest backend/test_evaluation.py
```
