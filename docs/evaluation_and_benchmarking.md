# VIDYA-X AI — Evaluation & Benchmarking Framework

**Step 13 — Evaluation, Benchmarking & Quality Assurance**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Dataset Format & Versioning](#dataset-format--versioning)
4. [Metric Definitions](#metric-definitions)
5. [Running Deterministic Tests](#running-deterministic-tests)
6. [Running Optional LLM-Based Evaluations](#running-optional-llm-based-evaluations)
7. [Benchmark CLI Runner](#benchmark-cli-runner)
8. [API Endpoints](#api-endpoints)
9. [Evaluation Dashboard](#evaluation-dashboard)
10. [Quality Gates & Release Policy](#quality-gates--release-policy)
11. [Interpreting Results](#interpreting-results)
12. [Comparing Runs](#comparing-runs)
13. [Environment Variables](#environment-variables)
14. [Known Limitations](#known-limitations)
15. [Which Metrics Require Human Review](#which-metrics-require-human-review)
16. [Disclaimer: Synthetic Benchmarks ≠ Educational Effectiveness](#disclaimer)

---

## Overview

The VIDYA-X AI Evaluation Framework provides a **reproducible, versioned benchmark suite** for the complete AI Tutor system — covering retrieval quality, grounded RAG answers, citation accuracy, unsupported-question abstention, quiz generation quality, personalization behavior, and study-plan scheduling feasibility.

All metric calculations are deterministic and run locally. LLM-judge integrations are optional and isolated behind a configuration flag.

---

## Architecture

```
backend/
└── evaluation/
    ├── __init__.py             # Package exports
    ├── config.py               # Paths, thresholds, gate definitions
    ├── schemas.py              # Pydantic models for cases, metrics, reports
    ├── dataset_loader.py       # Manifest loader + schema validator
    ├── metrics.py              # Recall@K, Precision@K, MRR, nDCG@K, …
    ├── retrieval_evaluator.py  # Semantic retrieval quality
    ├── citation_evaluator.py   # Citation ID resolution, metadata completeness
    ├── rag_evaluator.py        # Groundedness, abstention checks
    ├── quiz_evaluator.py       # Quiz & question-generation quality
    ├── personalization_evaluator.py  # Synthetic learner profiles A–H
    ├── study_planner_evaluator.py    # Time-budget & scheduling feasibility
    ├── synthetic_students.py   # Profile definitions (A–H)
    ├── report_generator.py     # Quality gate checking + artifact writer
    ├── evaluation_runner.py    # CLI & programmatic entry point
    └── datasets/
        ├── dataset_manifest.json
        ├── rag_cases.jsonl
        ├── retrieval_cases.jsonl
        ├── citation_cases.jsonl
        ├── quiz_cases.jsonl
        ├── personalization_cases.jsonl
        └── study_plan_cases.jsonl
```

Each run writes artifacts to:

```
evaluation_results/
└── run_<timestamp>/
    ├── run_metadata.json       # Run ID, timestamp, config, gate summary
    ├── case_results.jsonl      # Per-case pass/fail/score/message
    ├── metrics_summary.json    # Aggregated metric objects
    └── report.md               # Human-readable markdown report
```

---

## Dataset Format & Versioning

All cases use JSONL (one JSON object per line). Every case **must** include:

| Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | string | ✅ | Stable identifier (e.g. `rag_physics_001`) |
| `dataset_version` | string | ✅ | Matches `dataset_manifest.json` version |
| `task_type` | string | ✅ | `retrieval`, `rag`, `citation`, `quiz`, `personalization`, `study_plan` |
| `input` | object | ✅ | Task-specific input payload |
| `expected` | object | ✅ | Expected outcomes for metric calculation |
| `tags` | array | — | Labels (e.g. `["unsupported_question", "abstention"]`) |

### Example RAG case

```json
{
  "case_id": "rag_physics_001",
  "dataset_version": "1.0",
  "task_type": "rag",
  "course_id": "synthetic_physics",
  "question": "What relationship between force, mass, and acceleration is stated in the material?",
  "reference_answer": "The material states that net force equals mass multiplied by acceleration (F = ma).",
  "expected_source_ids": ["synthetic_physics_page_12"],
  "expected_supported": true,
  "tags": ["grounded_answer", "citation"]
}
```

### Example unsupported case

```json
{
  "case_id": "rag_unsupported_001",
  "dataset_version": "1.0",
  "task_type": "rag",
  "course_id": "synthetic_physics",
  "question": "What is the chemical composition of the atmosphere of Jupiter?",
  "reference_answer": null,
  "expected_source_ids": [],
  "expected_supported": false,
  "tags": ["unsupported_question", "abstention"]
}
```

### Versioning policy

- Increment the `version` in `dataset_manifest.json` when any case changes.
- Never modify stable cases in place — deprecate and add a new version instead.
- Metric comparisons across runs require identical dataset versions and metric definitions.

---

## Metric Definitions

### Retrieval Metrics (K = configurable, default 5)

| Metric | Definition | Denominator |
|---|---|---|
| **Recall@K** | Fraction of ground-truth relevant chunks appearing in the top-K results | Total relevant chunks in ground truth |
| **Precision@K** | Fraction of top-K results that are relevant | K |
| **Hit Rate@K** | 1 if any relevant chunk appears in top-K, else 0; averaged over cases | 1 per case |
| **MRR** | Mean Reciprocal Rank of the first relevant result | Number of cases |
| **nDCG@K** | Normalized Discounted Cumulative Gain using relevance grades | Ideal DCG at K |

### Citation Metrics

| Metric | Definition |
|---|---|
| **Citation Resolution Rate** | Fraction of cited chunk IDs that resolve to real retrieved source records |
| **Source Metadata Completeness** | Fraction of resolved sources with all required metadata fields present |
| **Citation Precision** | Fraction of citations relevant to the claim they support (requires judged labels) |
| **Citation Recall** | Fraction of gold-labeled required sources that were cited |
| **Cross-Course Violation Rate** | Fraction of citations linking to a chunk from a different course |

### RAG / Answer Quality Metrics

| Metric | Definition |
|---|---|
| **Abstention Rate** | Fraction of unsupported-question cases where the tutor correctly declines |
| **False Abstention Rate** | Fraction of supported-question cases where the tutor incorrectly declines |
| **Unsupported Answer Rate** | Fraction of unsupported cases where the tutor answers as if grounded |
| **Groundedness** | Whether factual claims are traceable to retrieved context (LLM judge, optional) |
| **Answer Relevance** | Whether the response answers the actual question (LLM judge, optional) |

### Quiz Quality Metrics

| Metric | Definition |
|---|---|
| **Valid Question Rate** | Fraction of generated questions passing structural validation |
| **Answer Key Correctness Rate** | Fraction of labeled test cases where the expected answer matches the key |
| **Citation Validity Rate** | Fraction of question citations that resolve to real source records |
| **Duplicate Question Rate** | Fraction of cases with near-identical questions in the same quiz |
| **Topic Alignment Rate** | Fraction of questions whose topic tag matches the requested topic |

### Personalization Metrics

| Metric | Definition |
|---|---|
| **Weak Topic Targeting Rate** | Profile B: Fraction of cases recommending the known weak prerequisite |
| **Cold Start Appropriateness** | Profile A: Whether diagnostic/balanced starter is recommended (not weak-topic specific) |
| **Mastery Progression Behavior** | Profile D/E: Correct reduction of remedial repetition as mastery improves |
| **Course Isolation Rate** | Profile H: Fraction of cases maintaining correct course boundary |

### Study Planner Metrics

| Metric | Definition |
|---|---|
| **Daily Budget Compliance Rate** | Fraction of planned days not exceeding the configured daily minute budget |
| **Exam Boundary Compliance Rate** | Fraction of plans with no tasks scheduled after the exam date |
| **Task Resource Link Rate** | Fraction of tasks linked to a valid course resource or activity |
| **Prerequisite Order Compliance** | Fraction of plans where prerequisite topics appear before dependent topics |

---

## Running Deterministic Tests

All deterministic tests run **without an external LLM API key**.

### Unit tests only

```powershell
cd "c:\Users\hp\Downloads\vidya - x"
python -m pytest backend/test_evaluation.py -v
```

Expected: **9/9 passed**.

### All backend tests

```powershell
python -m pytest backend/test_evaluation.py backend/test_study_plan.py backend/test_revision.py -v
```

Expected: **40/40 passed** (9 + 12 + 10 + any additional).

### Benchmark CLI runner (deterministic mode)

```powershell
cd "c:\Users\hp\Downloads\vidya - x\backend"
python -m evaluation.evaluation_runner
```

Options:

```powershell
# Smoke test — first 5 cases only
python -m evaluation.evaluation_runner --max-cases 5

# Specific task type
python -m evaluation.evaluation_runner --task-type retrieval

# Specific dataset version
python -m evaluation.evaluation_runner --dataset-version 1.0

# Custom output directory
python -m evaluation.evaluation_runner --output-dir ../evaluation_results/my_run
```

---

## Running Optional LLM-Based Evaluations

> ⚠️ LLM judge evaluations require a configured provider. They are **off by default** and never run in deterministic-only mode.

Set the following environment variables before running:

```powershell
$env:OPENAI_API_KEY = "sk-..."          # or your configured provider
$env:VIDYA_EVAL_LLM_JUDGE = "enabled"   # enables LLM judge metrics
$env:VIDYA_EVAL_MODEL = "gpt-4o-mini"   # LLM judge model
```

Then run without `--deterministic-only`:

```powershell
python -m evaluation.evaluation_runner --no-deterministic-only
```

LLM-judge results are stored with:
- Evaluator model name and version
- Prompt template hash/version
- Raw rationale text
- A clear marker that results are **model-judged, not ground truth**

Never treat an LLM judge's rating as a definitive correctness verdict.

---

## Benchmark CLI Runner

The runner is the programmatic entry point for all evaluation tasks.

**Module path:** `backend/evaluation/evaluation_runner.py`

**CLI invocation:**

```powershell
cd backend
python -m evaluation.evaluation_runner [options]
```

**Programmatic invocation (from Python):**

```python
from evaluation.evaluation_runner import run_evaluation

summary = run_evaluation(
    db=db_session,
    task_type=None,          # None = all tasks
    dataset_version="1.0",
    deterministic_only=True,
    max_cases=None,          # None = all cases
)
print(summary.model_dump())
```

The runner:

1. Validates the dataset manifest and all case schemas.
2. Loads the requested cases (filtered by task type and dataset version).
3. Records run configuration in `run_metadata.json`.
4. Executes the appropriate evaluator for each case.
5. Writes per-case results to `case_results.jsonl`.
6. Aggregates metrics and checks quality gates.
7. Writes `metrics_summary.json` and `report.md`.

Each run gets a unique timestamp-based ID. Prior runs are **never overwritten**.

---

## API Endpoints

All evaluation endpoints are under the `Evaluation & Benchmarks` tag in FastAPI docs (`/docs`).

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/evaluation/runs` | Trigger a new evaluation run |
| `GET`  | `/api/evaluation/runs` | List all saved runs (sorted by newest first) |
| `GET`  | `/api/evaluation/runs/{run_id}` | Full metadata for a specific run |
| `GET`  | `/api/evaluation/runs/{run_id}/metrics` | Aggregated metrics summary |
| `GET`  | `/api/evaluation/runs/{run_id}/cases` | Per-case results |

### POST /api/evaluation/runs request body

```json
{
  "task_type": null,
  "dataset_version": "1.0",
  "deterministic_only": true,
  "max_cases": null
}
```

> ⚠️ LLM-judge runs can be expensive. Set `max_cases` to limit scope when smoke-testing.

---

## Evaluation Dashboard

Open `frontend/pages/evaluation.html` in a browser while the backend is running on `localhost:8000`.

The dashboard provides:

- **Run trigger controls** — task type, dataset version, max cases, deterministic mode.
- **Run history table** — all saved runs with case counts and gate status.
- **Quality gate banner** — prominently shows pass/fail per run.
- **Metric category cards** — summarized scores for Retrieval, RAG, Citations, Quiz, Personalization, Study Planner.
- **Full metrics table** — all metric names, values, case counts, gate status, and definitions.
- **Case results table** — filterable by status and task type, with case IDs and messages.
- **Run metadata pane** — full JSON of run configuration, git commit, model identifiers.

**The dashboard never displays hardcoded mock scores.** All data comes from real evaluation run artifacts stored by the backend.

---

## Quality Gates & Release Policy

Quality gates are hard thresholds on critical metrics. A gate failure is a **release-blocking regression**.

Default gate thresholds (configured in `backend/evaluation/config.py`):

| Gate | Metric | Threshold |
|---|---|---|
| `citation_resolution` | Citation Resolution Rate | ≥ 0.90 |
| `course_isolation` | Cross-Course Violation Rate | ≤ 0.00 |
| `dataset_validity` | Dataset Schema Validity | = 1.00 |
| `abstention_behavior` | Abstention Rate (unsupported) | ≥ 0.80 |
| `quiz_validity` | Valid Question Rate | ≥ 0.85 |

A run report clearly states:

- ✅ **PASSED** — all configured gates cleared.
- ❌ **FAILED** — which gates failed, which cases caused the failure.
- ⚠️ **UNAVAILABLE** — required service or component not present.

**Do not modify gates or dataset cases to make a score look better.** A failing gate indicates a real quality regression.

---

## Interpreting Results

- **Percentage values** represent the fraction of cases meeting the criterion (0% – 100%).
- **N/A** means the metric could not be calculated (missing labels, unavailable service).
- **⚠️ Preliminary** labels indicate ≤ 5 cases — treat with caution.
- **Gate FAIL** on `course_isolation` means the RAG system returned cross-course material — this is a critical data-isolation bug.
- **Gate FAIL** on `citation_resolution` means generated answers cite IDs that do not correspond to real retrieved chunks — the citation system is fabricating references.

Do not interpret a high Recall@5 as proof that all retrieved content is relevant. Recall measures coverage; Precision measures accuracy. Both are needed.

---

## Comparing Runs

Two runs can only be meaningfully compared if they share:

- The same dataset version.
- The same metric definitions (evaluation package version).
- The same `deterministic_only` setting.
- For LLM metrics: the same evaluator model and prompt version.

The dashboard notes dataset version for each run. If versions differ, comparison may not be valid and will be flagged.

To compare two specific runs programmatically:

```python
import json

with open('evaluation_results/run_A/metrics_summary.json') as f:
    run_a = json.load(f)
with open('evaluation_results/run_B/metrics_summary.json') as f:
    run_b = json.load(f)

for key in run_a:
    va = run_a[key].get('value')
    vb = run_b[key].get('value')
    if va is not None and vb is not None:
        delta = float(vb) - float(va)
        print(f"{key}: {va:.3f} → {vb:.3f} ({delta:+.3f})")
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `OPENAI_API_KEY` | ❌ optional | Required for LLM judge / RAGAS integration |
| `VIDYA_EVAL_LLM_JUDGE` | ❌ optional | Set to `enabled` to activate LLM judge metrics |
| `VIDYA_EVAL_MODEL` | ❌ optional | LLM model name for judge (default: `gpt-4o-mini`) |
| `VIDYA_EVAL_OUTPUT_DIR` | ❌ optional | Override default `evaluation_results/` output path |

**Never store API keys in evaluation reports or datasets.**

---

## Known Limitations

1. **Synthetic dataset only.** The v1.0 dataset uses small synthetic course content (introductory Physics, Mathematics, Biology). Results on real course materials may differ significantly.

2. **No multimodal extraction evaluation.** Step 13 does not include OCR, diagram understanding, or video transcription metrics. These require reference files that are not bundled. They are tracked as `N/A` in reports.

3. **RAGAS integration is optional.** RAGAS LLM-based metrics (Answer Relevance, Faithfulness, Context Recall) require a configured LLM provider. They are skipped in `deterministic_only` mode.

4. **Personalization metrics are behavioral, not outcome-based.** The personalization evaluator checks whether the system behaves consistently with expected logic for synthetic profiles. It does not measure whether recommendations improve learning outcomes.

5. **LLM judge subjectivity.** When LLM-based grading is used, the evaluator's opinion is one signal, not ground truth. Rationale is stored but should not be treated as definitive.

6. **Small case counts.** The v1.0 dataset has a small number of cases per task type. Metrics are marked **preliminary** when computed over ≤ 5 cases.

7. **No adversarial test cases.** Prompt injection, jailbreaks, and adversarial inputs are not covered in the current benchmark.

---

## Which Metrics Require Human Review

The following metrics produce automated estimates that should be validated by a human reviewer before using results to make deployment decisions:

- **Groundedness / Faithfulness** — LLM judge output needs human spot-check.
- **Answer Relevance** — Automated scoring can miss nuance.
- **Short-answer rubric alignment** — Requires subject-matter expert review.
- **MCQ distractor plausibility** — Automated checks catch obvious issues; subtle ambiguity needs domain expert review.
- **Study-plan pedagogical soundness** — Feasibility metrics check scheduling logic, not whether the recommended order is educationally sound.

---

## Disclaimer

> **Synthetic benchmark performance does not guarantee real-world educational effectiveness.**

A high score on the v1.0 synthetic dataset indicates that the system correctly implements the intended logic for small, controlled examples. It does **not** prove:

- That the system will produce accurate answers on all real student questions.
- That adaptive recommendations will improve learning outcomes.
- That graded answers will be fair and accurate for all student responses.
- That study plans will lead to better exam performance.

Educational effectiveness claims require controlled human studies with real learners, which are outside the scope of this technical evaluation framework.
