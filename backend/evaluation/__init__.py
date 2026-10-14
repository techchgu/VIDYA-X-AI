"""
VIDYA-X AI — Evaluation & Benchmarking Package (Step 13)

Provides repeatable evaluation benchmarks, synthetic datasets, metrics, report generators,
and quality release gates for VIDYA-X AI.
"""

from .config import QUALITY_GATES, RESULTS_DIR
from .schemas import (
    DatasetCase,
    MetricResult,
    CaseEvaluationResult,
    QualityGateResult,
    EvaluationRunSummary,
)
from .dataset_loader import load_manifest, load_dataset_cases
from .evaluation_runner import run_evaluation

__all__ = [
    "QUALITY_GATES",
    "RESULTS_DIR",
    "DatasetCase",
    "MetricResult",
    "CaseEvaluationResult",
    "QualityGateResult",
    "EvaluationRunSummary",
    "load_manifest",
    "load_dataset_cases",
    "run_evaluation",
]
