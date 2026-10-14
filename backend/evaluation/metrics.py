"""
VIDYA-X AI — Deterministic Metric Calculators (Step 13)

Implements hand-verifiable, deterministic formulas for:
  - Retrieval: Recall@K, Precision@K, Hit Rate@K, MRR, nDCG@K
  - Citations: Resolution Rate, Metadata Completeness, Cross-Course Violation Count
  - Abstention: Unsupported-Question Abstention Rate, False Abstention Rate
  - Study Planner: Time Budget Compliance Rate, Exam Date Boundary Compliance Rate
"""

import math
from typing import List, Set, Dict, Any, Optional


def calculate_recall_at_k(actual_ids: List[str], expected_ids: List[str], k: int = 3) -> float:
    """Calculate Recall@K: fraction of relevant chunks retrieved in top K."""
    if not expected_ids:
        return 1.0 if not actual_ids else 1.0

    retrieved_k = set(actual_ids[:k])
    expected_set = set(expected_ids)
    hits = len(retrieved_k.intersection(expected_set))
    return round(hits / float(len(expected_set)), 4)


def calculate_precision_at_k(actual_ids: List[str], expected_ids: List[str], k: int = 3) -> float:
    """Calculate Precision@K: fraction of top K retrieved chunks that are relevant."""
    if k <= 0:
        return 0.0
    if not actual_ids:
        return 1.0 if not expected_ids else 0.0

    retrieved_k = set(actual_ids[:k])
    expected_set = set(expected_ids)
    hits = len(retrieved_k.intersection(expected_set))
    denom = min(k, len(actual_ids))
    return round(hits / float(denom), 4) if denom > 0 else 0.0


def calculate_hit_rate_at_k(actual_ids: List[str], expected_ids: List[str], k: int = 3) -> float:
    """Calculate Hit Rate@K: 1.0 if at least one expected chunk is retrieved in top K, else 0.0."""
    if not expected_ids:
        return 1.0

    retrieved_k = set(actual_ids[:k])
    expected_set = set(expected_ids)
    return 1.0 if len(retrieved_k.intersection(expected_set)) > 0 else 0.0


def calculate_mrr(actual_ids: List[str], expected_ids: List[str]) -> float:
    """Calculate Mean Reciprocal Rank (MRR): 1 / rank of first relevant chunk retrieved."""
    if not expected_ids:
        return 1.0

    expected_set = set(expected_ids)
    for idx, item in enumerate(actual_ids, 1):
        if item in expected_set:
            return round(1.0 / float(idx), 4)
    return 0.0


def calculate_ndcg_at_k(actual_ids: List[str], expected_ids: List[str], k: int = 3) -> float:
    """Calculate Normalized Discounted Cumulative Gain (nDCG@K)."""
    if not expected_ids:
        return 1.0

    expected_set = set(expected_ids)
    dcg = 0.0
    for idx, item in enumerate(actual_ids[:k], 1):
        rel = 1.0 if item in expected_set else 0.0
        dcg += rel / math.log2(idx + 1)

    # Calculate Ideal DCG (IDCG)
    idcg = 0.0
    for idx in range(1, min(k, len(expected_set)) + 1):
        idcg += 1.0 / math.log2(idx + 1)

    if idcg == 0.0:
        return 0.0
    return round(dcg / idcg, 4)
