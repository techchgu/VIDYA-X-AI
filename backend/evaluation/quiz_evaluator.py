"""
VIDYA-X AI — Quiz & Question Evaluator (Step 13)

Evaluates question generation quality, answer-key correctness, MCQ options format,
numerical answer tolerances, and question grounding/deduplication.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from services.question_verification_service import verify_question
from evaluation.schemas import DatasetCase, CaseEvaluationResult, MetricResult


def evaluate_quiz_cases(db: Session, cases: List[DatasetCase]) -> Dict[str, Any]:
    """
    Evaluate quiz cases for structural validity, answer key correctness, and grounding.
    """
    case_results = []
    valid_keys_count = 0
    valid_questions_count = 0

    for case in cases:
        inp = case.input_data or {}
        expected_supported = case.expected_supported

        # Run production question verification
        is_verified, errors = verify_question(db, inp)

        q_type = inp.get("question_type", "")
        corr_ans = inp.get("correct_answer", "")

        # Key correctness check
        key_valid = True
        if q_type == "mcq":
          opt_keys = {o.get("option_key") for o in inp.get("options", [])}
          if corr_ans not in opt_keys or not opt_keys:
              key_valid = False
        elif not corr_ans:
          key_valid = False

        if key_valid:
            valid_keys_count += 1
        if is_verified:
            valid_questions_count += 1

        case_passed = (is_verified == expected_supported)

        case_results.append(CaseEvaluationResult(
            case_id=case.case_id,
            task_type="quiz",
            passed=case_passed,
            score=1.0 if case_passed else 0.0,
            details={
                "is_verified": is_verified,
                "key_valid": key_valid,
                "expected_supported": expected_supported,
                "verification_errors": errors,
            },
        ))

    total = max(1, len(cases))
    key_rate = round(valid_keys_count / float(total), 4)
    valid_rate = round(valid_questions_count / float(total), 4)

    metrics = {
        "quiz_answer_key_correctness_rate": MetricResult(
            metric_name="quiz_answer_key_correctness_rate",
            category="Quiz Quality",
            definition="Fraction of generated questions with valid correct answer key",
            result=key_rate,
            benchmark_target=0.90,
            status="passed" if key_rate >= 0.80 else "failed",
            evaluated_cases_count=len(cases),
        ),
        "valid_question_rate": MetricResult(
            metric_name="valid_question_rate",
            category="Quiz Quality",
            definition="Fraction of questions passing all structural, option, and source grounding rules",
            result=valid_rate,
            benchmark_target=0.85,
            status="passed" if valid_rate >= 0.75 else "failed",
            evaluated_cases_count=len(cases),
        ),
    }

    return {
        "case_results": case_results,
        "metrics": metrics,
    }
