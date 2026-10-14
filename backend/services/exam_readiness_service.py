"""
VIDYA-X AI — Exam Readiness Engine Service (Step 12)

Summarizes available empirical evidence (BKT topic mastery, topic coverage, recent quiz accuracy,
unresolved misconceptions, remaining time) without overstating certainty.
Returns documented readiness categories: insufficient_data, needs_substantial_review, building_readiness, reasonably_prepared.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    Topic,
    LearnerTopicMastery,
    QuizAttempt,
    MisconceptionRecord,
    StudentStudyPreferences,
)

logger = logging.getLogger(__name__)


def evaluate_exam_readiness(
    db: Session,
    student_id: str,
    course_id: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evaluate student exam readiness based on empirical learner evidence.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    total_topics_count = len(topics)

    if total_topics_count == 0:
        return {
            "student_id": student_id,
            "course_id": course_id,
            "readiness_category": "insufficient_data",
            "category_label": "Insufficient Data",
            "category_description": "No course topics exist to evaluate readiness.",
            "confidence_indicator": "low",
            "average_mastery": 0.0,
            "topic_coverage_percentage": 0.0,
            "total_attempts_count": 0,
            "covered_topics": [],
            "topics_needing_attention": [],
            "active_misconceptions_count": 0,
            "days_until_exam": None,
            "suggested_next_steps": ["Upload course materials to generate topics and practice questions."],
            "evaluated_at": now.isoformat(),
        }

    # BKT Masteries
    bkt_rows = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id == course_id,
    ).all()
    bkt_map = {b.topic_id: b for b in bkt_rows if b.topic_id}

    # Attempts count
    attempts = db.query(QuizAttempt).filter(
        QuizAttempt.student_id == student_id,
        QuizAttempt.topic_id.in_([t.id for t in topics]),
    ).all()
    total_attempts_count = len(attempts)

    # Active misconceptions count
    active_misc_rows = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == student_id,
        MisconceptionRecord.course_id == course_id,
        MisconceptionRecord.status.in_(["supported", "under_review", "improving", "suspected"]),
    ).all()

    # Exam date from preferences
    prefs = db.query(StudentStudyPreferences).filter(
        StudentStudyPreferences.student_id == student_id,
        StudentStudyPreferences.course_id == course_id,
    ).first()

    days_until_exam = None
    if prefs and prefs.exam_date:
        ex_dt = prefs.exam_date
        if ex_dt.tzinfo is None:
            ex_dt = ex_dt.replace(tzinfo=timezone.utc)
        days_until_exam = max(0, (ex_dt - now).days)

    # Calculate metrics
    attempted_topics_count = sum(1 for t in topics if t.id in bkt_map and bkt_map[t.id].attempt_count > 0)
    topic_coverage_pct = round((attempted_topics_count / float(total_topics_count)) * 100, 1)

    mastery_sum = 0.0
    covered_topics = []
    topics_needing_attention = []

    for t in topics:
        bkt = bkt_map.get(t.id)
        if bkt and bkt.attempt_count > 0:
            m_val = bkt.mastery_probability
        else:
            m_val = 0.20  # default cold start

        mastery_sum += m_val

        if m_val >= 0.70:
            covered_topics.append(t.name)
        elif m_val < 0.50:
            reason = f"BKT mastery is {int(m_val * 100)}%"
            misc = next((m for m in active_misc_rows if m.topic_id == t.id), None)
            if misc:
                reason += f" (Misconception: {misc.title})"
            topics_needing_attention.append({
                "topic_id": t.id,
                "topic_name": t.name,
                "mastery_probability": round(m_val, 2),
                "reason": reason,
            })

    avg_mastery = round(mastery_sum / float(total_topics_count), 2)

    # Determine readiness category
    if total_attempts_count < 3 or topic_coverage_pct < 20.0:
        cat = "insufficient_data"
        label = "Insufficient Data"
        desc = "Complete more practice quizzes across course topics to establish a confident readiness estimate."
    elif avg_mastery < 0.45 or len(active_misc_rows) >= 3:
        cat = "needs_substantial_review"
        label = "Needs Substantial Review"
        desc = "Several foundational topics have low mastery or unresolved misconceptions. Focused study recommended."
    elif avg_mastery >= 0.75 and topic_coverage_pct >= 70.0 and len(active_misc_rows) <= 1:
        cat = "reasonably_prepared"
        label = "Reasonably Prepared"
        desc = "Strong mastery demonstrated across most course topics. Maintain momentum with spaced recall."
    else:
        cat = "building_readiness"
        label = "Building Readiness"
        desc = "Making solid progress, with key topics nearing target mastery. Address remaining weak areas."

    # Data completeness / confidence indicator
    if total_attempts_count >= 15 and topic_coverage_pct >= 70.0:
        confidence = "high"
    elif total_attempts_count >= 5 and topic_coverage_pct >= 40.0:
        confidence = "medium"
    else:
        confidence = "low"

    # Suggested Next Steps
    suggested_steps = []
    if active_misc_rows:
        suggested_steps.append(f"Work through remediation for '{active_misc_rows[0].title}'.")
    if topics_needing_attention:
        suggested_steps.append(f"Review weak topic '{topics_needing_attention[0]['topic_name']}'.")
    suggested_steps.append("Complete due spaced-repetition flashcards to retain learned concepts.")
    if days_until_exam is not None and days_until_exam <= 14:
        suggested_steps.append(f"Focus on exam practice sessions with {days_until_exam} days remaining.")

    return {
        "student_id": student_id,
        "course_id": course_id,
        "readiness_category": cat,
        "category_label": label,
        "category_description": desc,
        "confidence_indicator": confidence,
        "average_mastery": avg_mastery,
        "topic_coverage_percentage": topic_coverage_pct,
        "total_attempts_count": total_attempts_count,
        "covered_topics": covered_topics,
        "topics_needing_attention": topics_needing_attention,
        "active_misconceptions_count": len(active_misc_rows),
        "days_until_exam": days_until_exam,
        "suggested_next_steps": suggested_steps,
        "evaluated_at": now.isoformat(),
    }
