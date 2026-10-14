# VIDYA-X AI — Evaluation Action Plan & Benchmarking Protocol

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Purpose:** Actionable, reproducible evaluation roadmap to expand benchmark coverage before hackathon judging.  

---

## 1. Objectives & Scope
To provide judges with verifiable empirical confidence, this protocol establishes a lightweight benchmark battery leveraging the existing evaluation runner (`backend/evaluation/evaluation_runner.py`).

The battery tests 6 critical dimensions:
1. Grounded RAG accuracy & abstention
2. Citation metadata resolution
3. Quiz question answer-key validity
4. Personalization with synthetic learner profiles
5. Multimodal extraction provenance preservation
6. Safety & tenant isolation

---

## 2. Test Battery Specification

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BENCHMARK TEST BATTERY                          │
│                                                                        │
│  Dataset: backend/evaluation/datasets/                                 │
│  ├─ rag_cases.jsonl (15 cases: 10 supported, 5 unsupported)            │
│  ├─ citation_cases.jsonl (10 cases: PDF pages, PPT slides, timestamps) │
│  ├─ quiz_cases.jsonl (12 cases: 6 MCQ, 3 Short Answer, 3 Numerical)    │
│  ├─ personalization_cases.jsonl (8 synthetic students A–H)            │
│  └─ study_plan_cases.jsonl (6 student schedule constraints)            │
└────────────────────────────────────────────────────────────────────────┘
```

### A. Grounded RAG & Abstention Protocol
- **Supported Cases ($N=10$)**:
  - 5 exact keyword matches (e.g., *"What is Newton's Second Law?"*).
  - 3 paraphrase queries (e.g., *"How do force and acceleration relate to mass?"*).
  - 2 multi-chunk cross-topic queries (e.g., *"Compare static friction to kinetic friction on an inclined surface"*).
- **Unsupported Cases ($N=5$)**:
  - 3 out-of-domain science queries (e.g., *"How does mRNA translate into proteins?"*).
  - 2 plausible hallucinations (e.g., *"What is the seventh law of thermodynamics stated on slide 4?"*).
- **Success Criteria**:
  - Recall@3 $\ge 0.80$ on supported queries.
  - Abstention Rate $\ge 0.90$ on unsupported queries.
  - False Abstention Rate $\le 0.10$ on supported queries.

### B. Citation Verification Protocol
- **Target Cases ($N=10$)**:
  - Verify `file_name` matches uploaded artifact.
  - Verify `page_number` exists and lies within document boundaries ($1 \le \text{page} \le N$).
  - Verify `slide_number` corresponds to matching PPTX slide shape.
  - Verify `timestamp_start` and `timestamp_end` format is valid `HH:MM:SS` and start $<$ end.
- **Success Criteria**: Citation Resolution Rate $= 1.0 (100\%)$.

### C. Quiz Quality & Mathematical Validity
- **Target Cases ($N=12$)**:
  - **MCQ**: Check exactly 4 options provided, exactly one marked correct, distractors non-empty.
  - **Numerical**: Check target answer is a valid float, numerical tolerance specified ($> 0$), units specified (e.g., $\text{m/s}^2$).
  - **Short Answer**: Check reference key contains at least 3 required semantic concepts.
- **Success Criteria**: Answer-Key Validity Rate $= 1.0 (100\%)$.

### D. Personalization with Synthetic Students (Profiles A–H)
The evaluation suite includes 8 deterministic synthetic student archetypes:
- **Profile A (Novice)**: All topics $P(L) = 0.10 \implies$ Expected question difficulty: Introductory.
- **Profile B (Intermediate)**: Mixed mastery ($0.40 - 0.70$) $\implies$ Target intermediate items.
- **Profile C (Advanced)**: All topics $P(L) \ge 0.85 \implies$ Target challenge items.
- **Profile D (Impending Exam)**: Exam in 3 days $\implies$ Prioritize highest-weighted weak topics.
- **Profile E (Low Daily Time Budget)**: 15 min/day $\implies$ Tasks scheduled within $15 \pm 2$ minutes.
- **Profile F (Persistent Misconception)**: Repeated sign error on incline $\implies$ Flags supported misconception.
- **Profile G (Incline Mastery)**: Solves incline correctly $\implies$ Resolves misconception to inactive.
- **Profile H (Spaced Repetition)**: 5 flashcards rated 'Hard', 5 rated 'Easy' $\implies$ Escalates intervals appropriately.
- **Success Criteria**: Behavioral Alignment Rate $\ge 0.90$.

---

## 3. Execution Commands

```bash
# 1. Run deterministic benchmark suite
python -m unittest backend/test_evaluation.py

# 2. Re-run complete evaluation runner via CLI
python backend/evaluation/evaluation_runner.py --dataset-dir backend/evaluation/datasets --output-dir backend/evaluation_results/run_latest

# 3. View results in browser
# Open: http://localhost:8000/pages/evaluation.html
```
