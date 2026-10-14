"""
VIDYA-X AI — Study Planner & Spaced Repetition Evaluator (Step 13)

Evaluates daily study time budget compliance, exam date boundary enforcement,
spaced repetition interval growth, and task lifecycle tracking.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from services.spaced_repetition_service import calculate_next_review
from services.study_planner_service import generate_study_plan
from evaluation.schemas import DatasetCase, CaseEvaluationResult, MetricResult


def evaluate_study_plan_cases(db: Session, cases: List[DatasetCase]) -> Dict[str, Any]:
    """
    Evaluate study planner and spaced repetition engine rules on test cases.
    """
    case_results = []
    budget_compliant_days = 0
    total_days_evaluated = 0
    exam_boundary_violations = 0

    now = datetime.now(timezone.utc)

    for case in cases:
        inp = case.input_data or {}
        exp = case.expected_outcome or {}
        course_id = case.course_id
        student_id = f"eval_{case.case_id}"

        if "spaced_repetition" in case.tags:
            r_again = calculate_next_review("again", current_interval_days=1.0, review_count=1, now=now)
            r_hard = calculate_next_review("hard", current_interval_days=1.0, review_count=1, now=now)
            r_good = calculate_next_review("good", current_interval_days=1.0, review_count=1, now=now)
            r_easy = calculate_next_review("easy", current_interval_days=1.0, review_count=1, now=now)

            valid_order = (
                r_again["next_interval_days"] == 0.0 and
                r_hard["next_interval_days"] < r_good["next_interval_days"] < r_easy["next_interval_days"]
            )
            case_results.append(CaseEvaluationResult(
                case_id=case.case_id,
                task_type="study_plan",
                passed=valid_order,
                score=1.0 if valid_order else 0.0,
                details={"interval_order_valid": valid_order},
            ))
            continue

        horizon = inp.get("horizon_days", 7)
        budget = inp.get("daily_minutes_budget", 45)
        days_to_exam = inp.get("days_to_exam")

        exam_dt = now + timedelta(days=days_to_exam) if days_to_exam is not None else None

        plan = generate_study_plan(
            db=db,
            student_id=student_id,
            course_id=course_id,
            horizon_days=horizon,
            daily_minutes_budget=budget,
            exam_date=exam_dt,
            now=now,
        )

        plan_passed = True

        if isinstance(plan, dict) and "days" in plan:
            days = plan["days"]
            for d in days:
                total_days_evaluated += 1
                if d["planned_minutes"] <= budget:
                    budget_compliant_days += 1
                else:
                    plan_passed = False

            if days_to_exam is not None:
                if len(days) > days_to_exam:
                    plan_passed = False
                    exam_boundary_violations += 1

        case_results.append(CaseEvaluationResult(
            case_id=case.case_id,
            task_type="study_plan",
            passed=plan_passed,
            score=1.0 if plan_passed else 0.0,
            details={"days_count": len(plan.get("days", [])) if isinstance(plan, dict) else 0},
        ))

    tot_d = max(1, total_days_evaluated)
    budget_rate = round(budget_compliant_days / float(tot_d), 4) if total_days_evaluated > 0 else 1.0
    exam_compliance = 1.0 if exam_boundary_violations == 0 else 0.0

    metrics = {
        "daily_budget_compliance_rate": MetricResult(
            metric_name="daily_budget_compliance_rate",
            category="Study Planner Feasibility",
            definition="Fraction of scheduled study plan days respecting daily study time budget",
            result=budget_rate,
            benchmark_target=1.00,
            status="passed" if budget_rate == 1.00 else "failed",
            evaluated_cases_count=total_days_evaluated,
        ),
        "exam_date_boundary_compliance": MetricResult(
            metric_name="exam_date_boundary_compliance",
            category="Study Planner Feasibility",
            definition="Fraction of study plans strictly constraining task scheduling to date <= exam_date",
            result=exam_compliance,
            benchmark_target=1.00,
            status="passed" if exam_compliance == 1.00 else "failed",
            evaluated_cases_count=len(cases),
        ),
    }

    return {
        "case_results": case_results,
        "metrics": metrics,
    }
