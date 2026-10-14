"""
VIDYA-X AI — Citation Evaluator (Step 13)

Evaluates source citation ID resolution, page/slide/timestamp precision,
metadata completeness, and cross-course boundary violations.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from database.models import KnowledgeChunk
from services.revision_validation_service import resolve_and_validate_citations
from evaluation.schemas import DatasetCase, CaseEvaluationResult, MetricResult


def evaluate_citation_cases(db: Session, cases: List[DatasetCase]) -> Dict[str, Any]:
    """
    Evaluate citation cases against real course chunks and validation rules.
    """
    case_results = []
    total_citations = 0
    resolved_citations = 0
    metadata_complete_count = 0
    cross_course_violations = 0

    for case in cases:
        inp = case.input_data or {}
        citations_raw = inp.get("citations", [])
        expected_supported = case.expected_supported

        course_id = case.course_id

        resolved, is_valid = resolve_and_validate_citations(citations_raw, source_map={})

        case_passed = (is_valid == expected_supported)

        for cit in citations_raw:
            total_citations += 1
            chunk_id = cit.get("chunk_id")
            source_course_id = cit.get("course_id")

            # Check cross course violation
            if source_course_id and source_course_id != course_id:
                cross_course_violations += 1

            # Check resolution
            if chunk_id:
                chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()
                if chunk:
                    resolved_citations += 1
                    if chunk.course_id != course_id:
                        cross_course_violations += 1

            # Check metadata completeness
            has_page_slide_ts = any(
                cit.get(k) is not None for k in ["page", "slide", "timestamp_start"]
            )
            if has_page_slide_ts or cit.get("file_name"):
                metadata_complete_count += 1

        case_results.append(CaseEvaluationResult(
            case_id=case.case_id,
            task_type="citation",
            passed=case_passed,
            score=1.0 if case_passed else 0.0,
            details={
                "resolved_count": len(resolved),
                "citations_raw_count": len(citations_raw),
                "expected_supported": expected_supported,
            },
        ))

    total = max(1, total_citations)
    res_rate = round(resolved_citations / float(total), 4) if total_citations > 0 else 1.0
    meta_rate = round(metadata_complete_count / float(total), 4) if total_citations > 0 else 1.0

    metrics = {
        "citation_id_resolution_rate": MetricResult(
            metric_name="citation_id_resolution_rate",
            category="Citation Accuracy",
            definition="Fraction of generated citations resolving to valid database chunks",
            result=res_rate,
            benchmark_target=0.95,
            status="passed" if res_rate >= 0.90 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "source_metadata_completeness_rate": MetricResult(
            metric_name="source_metadata_completeness_rate",
            category="Citation Accuracy",
            definition="Fraction of citations with file name, page, slide, or timestamp metadata",
            result=meta_rate,
            benchmark_target=0.90,
            status="passed" if meta_rate >= 0.85 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "cross_course_citation_violation_count": MetricResult(
            metric_name="cross_course_citation_violation_count",
            category="Security & Boundaries",
            definition="Number of citations pointing to a different course than the request",
            result=float(cross_course_violations),
            benchmark_target=0.0,
            status="passed" if cross_course_violations == 0 else "failed",
            evaluated_cases_count=len(cases),
        ),
    }

    return {
        "case_results": case_results,
        "metrics": metrics,
    }
