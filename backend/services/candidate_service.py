"""
VIDYA-X AI — Candidate Question Retrieval Service (Step 9)

Finds, filters, and relaxes candidate questions from the course question bank
for adaptive question selection.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.models import Question, QuestionUsage, QuizAttempt


def get_candidate_questions(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
    limit: int = 50,
) -> List[Question]:
    """
    Retrieve candidate active questions for a given course from the database.
    Optionally filter by topic_id or concept_id.
    """
    query = db.query(Question).filter(
        Question.course_id == course_id,
        Question.status == "active",
    )

    if concept_id:
        query = query.filter(Question.concept_id == concept_id)
    elif topic_id:
        query = query.filter(Question.topic_id == topic_id)

    candidates = query.limit(limit).all()
    
    # If filtered candidate count is low and a specific concept/topic was requested,
    # expand to broader course candidates as backfill
    if len(candidates) < 5 and (concept_id or topic_id):
        fallback_query = db.query(Question).filter(
            Question.course_id == course_id,
            Question.status == "active",
        )
        existing_ids = {c.id for c in candidates}
        additional = [q for q in fallback_query.limit(limit).all() if q.id not in existing_ids]
        candidates.extend(additional)

    return candidates


def get_recently_used_questions(
    db: Session,
    student_id: str,
    course_id: str,
    window_hours: int = 72,
) -> Set[str]:
    """
    Find question IDs that the student has recently seen or attempted
    within the specified window_hours.
    """
    if not student_id:
        return set()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    # 1. Check QuestionUsage table
    usage_rows = db.query(QuestionUsage.question_id).filter(
        QuestionUsage.student_id == student_id,
        QuestionUsage.used_at >= cutoff,
    ).all()
    used_ids = {r[0] for r in usage_rows if r[0]}

    # 2. Check QuizAttempt table
    attempt_rows = db.query(QuizAttempt.question_id).filter(
        QuizAttempt.student_id == student_id,
        QuizAttempt.submitted_at >= cutoff,
    ).all()
    attempted_ids = {r[0] for r in attempt_rows if r[0]}

    return used_ids.union(attempted_ids)


def filter_and_relax_candidates(
    candidates: List[Question],
    recently_used_ids: Set[str],
    min_candidates: int = 3,
) -> List[Question]:
    """
    Filter out recently used questions.
    If the candidate count falls below min_candidates, gradually relax the filter.
    Do NOT fail simply because the student has seen every question.
    """
    fresh_candidates = [q for q in candidates if q.id not in recently_used_ids]

    if len(fresh_candidates) >= min_candidates or not candidates:
        return fresh_candidates

    # Relax filter: return fresh candidates first, followed by oldest/recycled candidates
    recycled = [q for q in candidates if q.id in recently_used_ids]
    return fresh_candidates + recycled


def get_recent_attempts_history(
    db: Session,
    student_id: str,
    course_id: str,
    limit: int = 20,
) -> List[QuizAttempt]:
    """
    Retrieve the student's recent QuizAttempt history for recency, failure scoring,
    and question type diversity analysis.
    """
    if not student_id:
        return []

    return db.query(QuizAttempt).filter(
        QuizAttempt.student_id == student_id,
    ).order_by(QuizAttempt.submitted_at.desc()).limit(limit).all()
