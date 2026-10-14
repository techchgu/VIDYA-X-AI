"""
VIDYA-X AI — Benchmark Evaluation Runner (Step 13)

Command-line & programmatic entry point for running reproducible benchmark evaluation suites.

Usage:
  python -m evaluation.evaluation_runner
"""

import argparse
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from evaluation.config import DEFAULT_DATASET_VERSION, RESULTS_DIR
from evaluation.dataset_loader import load_dataset_cases, load_manifest
from evaluation.schemas import EvaluationRunSummary, CaseEvaluationResult, MetricResult
from evaluation.retrieval_evaluator import evaluate_retrieval_cases
from evaluation.citation_evaluator import evaluate_citation_cases
from evaluation.rag_evaluator import evaluate_rag_cases
from evaluation.quiz_evaluator import evaluate_quiz_cases
from evaluation.personalization_evaluator import evaluate_personalization_cases
from evaluation.study_planner_evaluator import evaluate_study_plan_cases
from evaluation.report_generator import generate_evaluation_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_evaluation(
    db: Session,
    task_type: Optional[str] = None,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    deterministic_only: bool = True,
    max_cases: Optional[int] = None,
    run_id: Optional[str] = None,
) -> EvaluationRunSummary:
    """
    Execute full benchmark evaluation suite.
    """
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    logger.info(f"Starting evaluation benchmark run '{run_id}' (dataset_version={dataset_version})...")

    # Load dataset cases
    cases = load_dataset_cases(
        task_type=task_type,
        dataset_version=dataset_version,
        max_cases=max_cases,
    )

    all_case_results: List[CaseEvaluationResult] = []
    all_metrics: Dict[str, MetricResult] = {}

    # Separate cases by task_type
    retrieval_cases = [c for c in cases if c.task_type == "retrieval"]
    rag_cases = [c for c in cases if c.task_type == "rag"]
    citation_cases = [c for c in cases if c.task_type == "citation"]
    quiz_cases = [c for c in cases if c.task_type == "quiz"]
    personalization_cases = [c for c in cases if c.task_type == "personalization"]
    study_plan_cases = [c for c in cases if c.task_type == "study_plan"]

    # 1. Evaluate Retrieval
    if retrieval_cases:
        res = evaluate_retrieval_cases(db, retrieval_cases)
        all_case_results.extend(res["case_results"])
        all_metrics.update(res["metrics"])

    # 2. Evaluate Grounded RAG
    if rag_cases:
        res = evaluate_rag_cases(db, rag_cases)
        all_case_results.extend(res["case_results"])
        all_metrics.update(res["metrics"])

    # 3. Evaluate Citations
    if citation_cases:
        res = evaluate_citation_cases(db, citation_cases)
        all_case_results.extend(res["case_results"])
        all_metrics.update(res["metrics"])

    # 4. Evaluate Quiz Quality
    if quiz_cases:
        res = evaluate_quiz_cases(db, quiz_cases)
        all_case_results.extend(res["case_results"])
        all_metrics.update(res["metrics"])

    # 5. Evaluate Personalization
    if personalization_cases:
        res = evaluate_personalization_cases(db, personalization_cases)
        all_case_results.extend(res["case_results"])
        all_metrics.update(res["metrics"])

    # 6. Evaluate Study Planner
    if study_plan_cases:
        res = evaluate_study_plan_cases(db, study_plan_cases)
        all_case_results.extend(res["case_results"])
        all_metrics.update(res["metrics"])

    # Generate Report Artifacts
    summary = generate_evaluation_report(
        run_id=run_id,
        dataset_version=dataset_version,
        deterministic_only=deterministic_only,
        case_results=all_case_results,
        metrics=all_metrics,
    )

    logger.info(f"Evaluation run '{run_id}' completed. Pass rate: {summary.pass_rate_percentage}%")
    return summary


def main():
    parser = argparse.ArgumentParser(description="VIDYA-X AI Benchmark Evaluation Runner")
    parser.add_argument("--task-type", type=str, help="Filter by task type (rag, retrieval, citation, quiz, personalization, study_plan)")
    parser.add_argument("--dataset-version", type=str, default=DEFAULT_DATASET_VERSION, help="Dataset version tag")
    parser.add_argument("--max-cases", type=int, help="Limit maximum cases evaluated (for smoke testing)")
    parser.add_argument("--run-id", type=str, help="Custom run identifier")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = run_evaluation(
            db=db,
            task_type=args.task_type,
            dataset_version=args.dataset_version,
            deterministic_only=True,
            max_cases=args.max_cases,
            run_id=args.run_id,
        )
        print(f"\n=======================================================")
        print(f"  VIDYA-X AI Benchmark Evaluation Summary")
        print(f"=======================================================")
        print(f"  Run ID:                {summary.run_id}")
        print(f"  Total Cases Evaluated: {summary.total_cases}")
        print(f"  Passed Cases:          {summary.passed_cases}")
        print(f"  Failed Cases:          {summary.failed_cases}")
        print(f"  Pass Rate:             {summary.pass_rate_percentage}%")
        print(f"  Quality Release Gates: {'PASSED ✅' if summary.quality_gates_passed else 'FAILED ❌'}")
        print(f"=======================================================\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
