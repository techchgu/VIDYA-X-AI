# VIDYA-X AI Benchmark Evaluation Report

**Run ID:** `test_suite_run_001`  
**Timestamp:** `2026-10-13T10:26:40.433120+00:00`  
**Dataset Version:** `1.0`  
**Mode:** `Deterministic-Only`  
**Overall Quality Release Gate:** ✅ PASSED  

---

## 1. Benchmark Execution Summary

| Metric | Value |
| :--- | :---: |
| **Total Cases Evaluated** | 10 |
| **Passed Cases** | 3 |
| **Failed Cases** | 7 |
| **Pass Rate** | **30.0%** |

---

## 2. Quality Release Gates

| Gate Name | Metric | Required Threshold | Actual Measured | Gate Status |
| :--- | :--- | :---: | :---: | :---: |
| Gate: course_isolation_violation_count | `course_isolation_violation_count` | `0.0` | `0.0` | ✅ PASSED |
| Gate: unsupported_question_abstention_rate | `unsupported_question_abstention_rate` | `0.85` | `1.0` | ✅ PASSED |

---

## 3. Aggregated System Metrics

| Metric Name | Category | Measured Result | Benchmark Target | Metric Status |
| :--- | :--- | :---: | :---: | :---: |
| `recall_at_k` | Retrieval Quality | **0.2** | 0.8 | ❌ FAILED |
| `precision_at_k` | Retrieval Quality | **0.2** | 0.6 | ❌ FAILED |
| `hit_rate_at_k` | Retrieval Quality | **0.2** | 0.9 | ❌ FAILED |
| `mrr` | Retrieval Quality | **0.2** | 0.85 | ❌ FAILED |
| `course_isolation_violation_count` | Security & Boundaries | **0.0** | 0.0 | ✅ PASSED |
| `unsupported_question_abstention_rate` | RAG & Abstention Quality | **1.0** | 0.85 | ✅ PASSED |
| `grounded_answer_accuracy` | RAG & Abstention Quality | **0.0** | 0.9 | ❌ FAILED |
| `false_abstention_rate` | RAG & Abstention Quality | **1.0** | 0.1 | ❌ FAILED |

---

## 4. Case-by-Case Execution Details

| Case ID | Task Type | Outcome | Score | Details |
| :--- | :--- | :---: | :---: | :--- |
| `ret_physics_001` | `retrieval` | ❌ FAIL | `0.0` | recall_at_k=0.0, precision_at_k=0.0, hit_rate_at_k=0.0, mrr= |
| `ret_physics_002` | `retrieval` | ❌ FAIL | `0.0` | recall_at_k=0.0, precision_at_k=0.0, hit_rate_at_k=0.0, mrr= |
| `ret_bio_001` | `retrieval` | ❌ FAIL | `0.0` | recall_at_k=0.0, precision_at_k=0.0, hit_rate_at_k=0.0, mrr= |
| `ret_math_001` | `retrieval` | ❌ FAIL | `0.0` | recall_at_k=0.0, precision_at_k=0.0, hit_rate_at_k=0.0, mrr= |
| `ret_isolation_001` | `retrieval` | ✅ PASS | `1.0` | recall_at_k=1.0, precision_at_k=1.0, hit_rate_at_k=1.0, mrr= |
| `rag_physics_001` | `rag` | ❌ FAIL | `0.0` | expected_supported=True, chunks_retrieved_count=0, abstained |
| `rag_physics_002` | `rag` | ❌ FAIL | `0.0` | expected_supported=True, chunks_retrieved_count=0, abstained |
| `rag_bio_001` | `rag` | ❌ FAIL | `0.0` | expected_supported=True, chunks_retrieved_count=0, abstained |
| `rag_unsupported_001` | `rag` | ✅ PASS | `1.0` | expected_supported=False, chunks_retrieved_count=0, abstaine |
| `rag_unsupported_002` | `rag` | ✅ PASS | `1.0` | expected_supported=False, chunks_retrieved_count=0, abstaine |
