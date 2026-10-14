# VIDYA-X AI — Evaluation & Benchmarking Summary Report

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Track:** Multimodal AI Hackathon 2026 — Track D: Personalized Tutoring & Adaptive Learning  
**Evaluation Framework Version:** 1.0 (Step 13)  
**Latest Evaluated Benchmark Run ID:** `test_suite_run_001`  
**Execution Timestamp:** 2026-10-13T07:24:31Z (Automated Local Benchmark Run)  

---

## 1. Executive Summary & Evaluation Philosophy

In educational AI, **software test passing is necessary but not sufficient to prove pedagogical effectiveness**. Unit tests prove code paths do not throw unhandled exceptions; empirical evaluations measure whether retrieval finds relevant materials, citations point to accurate pages, answers abstain when information is missing, and study schedules are realistic.

VIDYA-X AI features a built-in, reproducible evaluation suite located in `backend/evaluation/`. It executes versioned JSONL test cases against the live services and writes structured artifacts (`run_metadata.json`, `case_results.jsonl`, `metrics_summary.json`, `report.md`).

---

## 2. Actual Measured Results (Run: `test_suite_run_001`)

The following metrics represent actual measured outcomes from the automated deterministic benchmark run stored in `backend/evaluation_results/run_test_suite_run_001/`:

| Metric Name | Category | Measured Result | Benchmark Target | Evaluated Cases Count | Evaluation Mode | Gate / Status |
|---|---|:---:|:---:|:---:|---|:---:|
| **`course_isolation_violation_count`** | Security & Privacy | **0.0** | 0.0 | 5 cases | Deterministic vector filter validation | ✅ **PASSED** (Quality Gate) |
| **`unsupported_question_abstention_rate`** | Safety & Hallucination Prevention | **1.0 (100%)** | 0.85 (85%) | 2 cases | Calibrated similarity & lexical threshold check | ✅ **PASSED** (Quality Gate) |
| **`recall_at_k` ($k=3$)** | Retrieval Relevance | **0.20 (20%)** | 0.80 (80%) | 5 queries | Exact chunk ID overlap against synthetic test ground truth | ❌ *Below Target* |
| **`precision_at_k` ($k=3$)** | Retrieval Precision | **0.20 (20%)** | 0.60 (60%) | 5 queries | Fraction of top-3 retrieved chunks marked relevant | ❌ *Below Target* |
| **`hit_rate_at_k` ($k=3$)** | Retrieval Hit Rate | **0.20 (20%)** | 0.90 (90%) | 5 queries | Fraction of queries where $\ge 1$ relevant chunk was returned | ❌ *Below Target* |
| **`mrr` (Mean Reciprocal Rank)** | Retrieval Rank Quality | **0.20** | 0.85 | 5 queries | Reciprocal rank of first ground-truth relevant chunk | ❌ *Below Target* |
| **`grounded_answer_accuracy`** | RAG Grounding | **0.00** | 0.90 | 3 cases | Automated ground-truth answer phrase match | ❌ *Below Target (due to abstention)* |
| **`false_abstention_rate`** | Availability & Coverage | **1.00 (100%)** | 0.10 (10%) | 3 cases | Supported questions declined due to strict conservative threshold | ❌ *Below Target* |

---

## 3. Honest Engineering Analysis of Findings

### 3.1 What Passed and Why It Matters
1. **Course Isolation (Violation Count: 0.0)**: In multi-tenant educational platforms, a student studying Biology must never see Physics chunks, and Student A must never see Student B's materials. The system enforces strict SQL `WHERE course_id = :course_id` filtering prior to vector ranking, guaranteeing zero cross-course leakage.
2. **Safe Abstention on Unsupported Queries (100%)**: When queries like *"Explain photosynthesis"* were asked against the Physics material, the system declined 100% of the time. The tutor did not hallucinate an explanation.

### 3.2 Root Cause of Low Retrieval & False Abstention in Test Run 001
- **Local Embedding Vector Characteristics**: In the local deterministic test mode (`EMBEDDING_PROVIDER=local`), embeddings are computed via lightweight character n-gram feature hashes to avoid downloading multi-gigabyte PyTorch transformer models during automated CI.
- **Threshold Calibration**: Because n-gram cosine similarities are compressed into a narrower range than dense neural vectors (e.g., SentenceTransformers `all-MiniLM-L6-v2`), the conservative abstention threshold (originally 0.25) caused the tutor to treat relevant in-domain chunks as borderline, triggering safe abstention.
- **Resolution**: In production environments, VIDYA-X AI connects to dense pgvector embeddings where cosine similarity distributions are well-separated. Furthermore, the hybrid similarity/lexical threshold was subsequently calibrated in Step 15 to prevent false abstentions on supported queries.

---

## 4. Test Suite Pass Rates vs. Pedagogical Verification

| Verification Level | Scope | Status | Evidence |
|---|---|:---:|---|
| **Unit & Service Correctness** | Pytest backend test suite | **68 / 68 Passed (100%)** | Full execution across `test_adaptive.py`, `test_api.py`, `test_bkt.py`, `test_quiz.py`, `test_revision.py`, `test_study_plan.py`, `test_visuals.py`, `test_extraction.py`, `test_integration.py`. |
| **API Contract & Health** | FastAPI endpoints & health probes | **4 / 4 Passed (100%)** | `test_api.py` verifies `/health` (200), `/health/ready` (200/503), `/health/ai` (200), and `/api/upload` (200/400). |
| **BKT Mathematical Invariants** | Bayesian Knowledge Tracing updates | **26 / 26 Passed (100%)** | `test_bkt.py` verifies monotonic mastery increases on success, decreases on failure, bounds $[0.0, 1.0]$, slip/guess damping. |
| **Question Deduplication** | SHA-256 fingerprint deduplication | **13 / 13 Passed (100%)** | `test_quiz.py` verifies exact duplicate questions are caught and excluded. |
| **Student Learning Gains** | Empirical pre/post student test score improvements | **NOT MEASURED YET** | Requires multi-week longitudinal randomized controlled trial with human students; not claimable in a hackathon context. |
