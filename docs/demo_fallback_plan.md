# VIDYA-X AI — Live Demonstration Fallback & Resilience Protocol

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Purpose:** Comprehensive guide for running a reliable live hackathon demo and handling real-world presentation contingencies (Wi-Fi loss, API rate limits, slow processing).

---

## 1. Primary Live Demo Path (The "Happy Path")

Use this sequence whenever local server and internet connectivity are stable:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRIMARY LIVE DEMO FLOW                          │
│                                                                        │
│  1. Open Dashboard: http://localhost:8000/pages/dashboard.html         │
│  2. Click "⚡ Demo Mode" button in the navigation header                │
│  3. Navigate to "AI Tutor" -> Ask Newton's Second Law                  │
│  4. Click citation badge [1] -> View Page 2 excerpt                    │
│  5. Ask out-of-domain photosynthesis question -> Show Safe Abstention │
│  6. Navigate to "Quiz Studio" -> Complete 2 adaptive practice items    │
│  7. View "Progress" -> Show BKT mastery update                         │
│  8. View "Remediation" -> Show Incline Normal Force misconception     │
│  9. View "Flashcards & Study Plan" -> Show 3D card & scheduled tasks   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Contingency Fallback Levels

| Level | Condition | Fallback Action | Labeling Policy |
|:---:|---|---|---|
| **Tier 1 (Normal)** | Local server running, Cloud LLM active | Run live queries in real time. | Real-time live AI generation. |
| **Tier 2 (Degraded)** | Local server running, Cloud API down or Wi-Fi lost | Toggle **⚡ Demo Mode**. Seed fixtures generate instant responses and deterministic BKT updates. | Disclose: *"Demonstrating via deterministic local knowledge fixtures."* |
| **Tier 3 (Offline)** | Python environment or backend crash | Open pre-cached static frontend in browser or review evaluation artifacts in `backend/evaluation_results/`. | Disclose: *"Showing pre-computed verified run artifacts from test suite."* |

---

## 3. How to Reset Demo Data in 5 Seconds

If a test attempt leaves the demo profile in an unwanted state:
1. Click the yellow banner at the top of the screen: **"Reset Demo Data"** (or make a `POST /api/demo/reset` request via Swagger at `/docs`).
2. This resets `course_demo_physics` and `student_demo` back to baseline:
   - 4 foundational knowledge chunks indexed.
   - BKT mastery set to clean baseline ($P(L) = 0.50$ for Newton's Laws, $0.35$ for Friction).
   - 1 active supported misconception (*Normal force on inclines*).
   - 5 active flashcards scheduled.
3. Real user data and other custom courses are completely unaffected due to strict `course_id` isolation.

---

## 4. Specific Failure Recovery Procedures

### Scenario A: Upload Processing Hangs or Takes Too Long
- **Cause**: Parsing a multi-megabyte PDF or running CPU whisper on a 20-minute video live during a 6-minute pitch.
- **Recovery**: Do not upload a 100MB file live. Instead, use the pre-processed sample material already present in the demo course (`Newton_Laws_of_Motion_Lecture_Notes.pdf`), and explain:
  > *"To respect our 6-minute presentation window, we have already indexed our 4-page Classical Mechanics lecture deck. Let's inspect the extracted chunks."*

### Scenario B: AI Tutor Returns Safe Abstention for an In-Domain Question
- **Cause**: Slight phrasing mismatch when running with local lightweight n-gram embeddings.
- **Recovery**: Use the preset prompt chip in the tutor UI: *"What is Newton's Second Law relating net force, mass, and acceleration?"*. Explain:
  > *"Because our local testing mode uses a strict conservative similarity gate to prevent hallucinations, queries closely aligned with course terminology yield verified citations."*

### Scenario C: Rate Limit on Vision API
- **Cause**: Gemini 1.5 Flash API key exceeds quota or has network latency.
- **Recovery**: Navigate to `visuals.html`. The system automatically renders extracted visual assets with local structured descriptions and labels extracted during ingestion. Explain:
  > *"Our visual engine includes a local heuristic fallback so students can browse diagrams and equations even when offline."*

---

## 5. Security & Privacy Rules During Demo
- **Never display raw `.env` files** or terminal windows showing `GEMINI_API_KEY` on the projection screen.
- Use the `/health/ai` endpoint to prove AI availability without showing secret keys.
- Do not demonstrate using real student private names or proprietary unreleased university exams.
