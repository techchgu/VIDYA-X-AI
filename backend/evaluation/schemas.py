"""
VIDYA-X AI — Evaluation Schemas & Pydantic Data Models (Step 13)

Defines data models for test cases, metric results, evaluation case runs, and summary reports.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DatasetCase(BaseModel):
    """A single evaluation benchmark case from the dataset."""
    case_id: str
    dataset_version: str = "1.0"
    task_type: str  # rag | retrieval | citation | quiz | personalization | study_plan
    course_id: str
    question: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    reference_answer: Optional[str] = None
    expected_source_ids: Optional[List[str]] = Field(default_factory=list)
    expected_supported: bool = True
    expected_outcome: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)


class MetricResult(BaseModel):
    """Result of a single calculated metric."""
    metric_name: str
    category: str
    definition: str
    result: float
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    benchmark_target: Optional[float] = None
    status: str = "passed"  # passed | failed | unavailable
    evaluated_cases_count: int = 0


class CaseEvaluationResult(BaseModel):
    """Detailed evaluation result for an individual case."""
    case_id: str
    task_type: str
    passed: bool
    score: float = 1.0
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class QualityGateResult(BaseModel):
    """Result of a quality release gate check."""
    gate_name: str
    metric_name: str
    threshold: float
    actual_value: float
    passed: bool


class EvaluationRunSummary(BaseModel):
    """Overall summary of an evaluation benchmark run."""
    run_id: str
    dataset_version: str
    timestamp: str
    deterministic_only: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate_percentage: float
    metrics: Dict[str, MetricResult] = Field(default_factory=dict)
    quality_gates: List[QualityGateResult] = Field(default_factory=list)
    quality_gates_passed: bool
    gate_failures: List[str] = Field(default_factory=list)
