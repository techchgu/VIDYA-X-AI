"""
VIDYA-X AI — Retrieval Evaluator (Step 13)

Evaluates semantic vector retrieval quality (Recall@K, Precision@K, Hit Rate@K, MRR, nDCG@K)
and checks cross-course retrieval leakage boundaries.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from database.models import KnowledgeChunk
from services.search_service import semantic_search
from evaluation.schemas import DatasetCase, CaseEvaluationResult, MetricResult
from evaluation.metrics import (
    calculate_recall_at_k,
    calculate_precision_at_k,
    calculate_hit_rate_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
)


def evaluate_retrieval_cases(db: Session, cases: List[DatasetCase], k: int = 3) -> Dict[str, Any]:
    """
    Run semantic retrieval evaluation on a list of retrieval cases.
    """
    case_results = []
    recalls, precisions, hit_rates, mrrs, ndcgs = [], [], [], [], []
    leakage_violations = 0

    for case in cases:
        query_text = case.question or ""
        expected_ids = case.expected_source_ids or []
        course_id = case.course_id

        # Execute production semantic search
        retrieved_chunks = semantic_search(db=db, course_id=course_id, query=query_text, top_k=k)
        retrieved_ids = [c.id for c in retrieved_chunks if hasattr(c, "id")]

        # Check cross-course leakage
        for c in retrieved_chunks:
            if hasattr(c, "course_id") and c.course_id and c.course_id != course_id:
                leakage_violations += 1

        rec = calculate_recall_at_k(retrieved_ids, expected_ids, k=k)
        prec = calculate_precision_at_k(retrieved_ids, expected_ids, k=k)
        hit = calculate_hit_rate_at_k(retrieved_ids, expected_ids, k=k)
        mrr = calculate_mrr(retrieved_ids, expected_ids)
        ndcg = calculate_ndcg_at_k(retrieved_ids, expected_ids, k=k)

        recalls.append(rec)
        precisions.append(prec)
        hit_rates.append(hit)
        mrrs.append(mrr)
        ndcgs.append(ndcg)

        passed = hit == 1.0 if expected_ids else len(retrieved_ids) == 0
        case_results.append(CaseEvaluationResult(
            case_id=case.case_id,
            task_type="retrieval",
            passed=passed,
            score=hit,
            details={
                "recall_at_k": rec,
                "precision_at_k": prec,
                "hit_rate_at_k": hit,
                "mrr": mrr,
                "ndcg_at_k": ndcg,
                "retrieved_ids": retrieved_ids,
                "expected_ids": expected_ids,
            },
        ))

    total = len(cases) if cases else 1
    avg_recall = round(sum(recalls) / float(total), 4) if recalls else 0.0
    avg_precision = round(sum(precisions) / float(total), 4) if precisions else 0.0
    avg_hit_rate = round(sum(hit_rates) / float(total), 4) if hit_rates else 0.0
    avg_mrr = round(sum(mrrs) / float(total), 4) if mrrs else 0.0
    avg_ndcg = round(sum(ndcgs) / float(total), 4) if ndcgs else 0.0

    metrics = {
        "recall_at_k": MetricResult(
            metric_name="recall_at_k",
            category="Retrieval Quality",
            definition=f"Fraction of relevant chunks retrieved in top {k}",
            result=avg_recall,
            benchmark_target=0.80,
            status="passed" if avg_recall >= 0.70 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "precision_at_k": MetricResult(
            metric_name="precision_at_k",
            category="Retrieval Quality",
            definition=f"Fraction of top {k} retrieved chunks that are relevant",
            result=avg_precision,
            benchmark_target=0.60,
            status="passed" if avg_precision >= 0.50 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "hit_rate_at_k": MetricResult(
            metric_name="hit_rate_at_k",
            category="Retrieval Quality",
            definition=f"Fraction of queries where at least 1 relevant chunk was in top {k}",
            result=avg_hit_rate,
            benchmark_target=0.90,
            status="passed" if avg_hit_rate >= 0.80 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "mrr": MetricResult(
            metric_name="mrr",
            category="Retrieval Quality",
            definition="Mean Reciprocal Rank of first relevant chunk retrieved",
            result=avg_mrr,
            benchmark_target=0.85,
            status="passed" if avg_mrr >= 0.70 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "course_isolation_violation_count": MetricResult(
            metric_name="course_isolation_violation_count",
            category="Security & Boundaries",
            definition="Number of chunks retrieved from a foreign course ID",
            result=float(leakage_violations),
            benchmark_target=0.0,
            status="passed" if leakage_violations == 0 else "failed",
            evaluated_cases_count=len(cases),
        ),
    }

    return {
        "case_results": case_results,
        "metrics": metrics,
    }
