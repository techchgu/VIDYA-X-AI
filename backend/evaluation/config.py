"""
VIDYA-X AI — Evaluation & Benchmarking Configuration (Step 13)

Configures dataset paths, evaluation output directories, quality release gate thresholds,
and evaluator settings.
"""

import os

EVALUATION_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(EVALUATION_DIR, "datasets")
RESULTS_DIR = os.path.join(os.path.dirname(EVALUATION_DIR), "evaluation_results")

# Ensure results directory exists
os.makedirs(RESULTS_DIR, exist_ok=True)

DEFAULT_DATASET_VERSION = "1.0"
DEFAULT_RETRIEVAL_K = 3

# Quality Release Gate Thresholds
QUALITY_GATES = {
    "citation_id_resolution_rate": 0.95,      # >= 95% of citations must resolve to real chunks
    "course_isolation_violation_count": 0,    # 0 cross-course leakage allowed
    "unsupported_question_abstention_rate": 0.85, # >= 85% of unsupported questions correctly abstained
    "daily_budget_compliance_rate": 1.00,     # 100% of generated plan days must respect time budget
    "exam_date_boundary_compliance": 1.00,    # 100% of generated plan days must be <= exam date
    "quiz_answer_key_correctness_rate": 0.90,  # >= 90% of question answer keys valid
}
