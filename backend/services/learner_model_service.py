"""
VIDYA-X AI — Learner Model Service (Step 8)

Connects quiz attempts to BKT learner-state updates.
Only updates mastery AFTER a verified answer evaluation.

This service bridges:
  quiz_service.submit_answer()  →  update_learner_after_attempt()
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from database.models import (
    LearnerTopicMastery,
    LearnerConceptMastery,
    Question,
    Topic,
    Concept,
)
from services.bkt_service import (
    BKT_INITIAL_MASTERY,
    update_bkt,
    update_bkt_with_evidence,
    classify_mastery,
)


def update_learner_after_attempt(
    db: Session,
    student_id: str,
    course_id: str,
    question_id: str,
    is_correct: bool,
    score: float = 1.0,
) -> Dict[str, Any]:
    """
    Update the learner model (topic + concept mastery) after a verified answer.

    Args:
        db:          SQLAlchemy session.
        student_id:  Student identifier.
        course_id:   Course identifier (for isolation).
        question_id: The question that was answered.
        is_correct:  Boolean result of evaluation.
        score:       Continuous score in [0.0, 1.0] (used for partial credit).

    Returns:
        dict with 'topic' and 'concept' mastery update results.
    """
    now = datetime.now(timezone.utc)

    # 1. Retrieve the question for topic/concept metadata
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        return {"error": f"Question '{question_id}' not found"}

    topic_id   = q.topic_id
    concept_id = q.concept_id

    # 2. Determine BKT evidence (support partial credit for short_answer)
    if q.question_type == "short_answer":
        # Use continuous evidence: score is already in [0.0, 1.0]
        evidence = float(score) if score is not None else (1.0 if is_correct else 0.0)
    else:
        # MCQ and numerical: binary correct/incorrect
        evidence = 1.0 if is_correct else 0.0

    # 3. Update topic-level mastery
    topic_result = None
    if topic_id:
        topic_result = _update_topic_mastery(db, student_id, course_id, topic_id, evidence, now)

    # 4. Update concept-level mastery
    concept_result = None
    if concept_id:
        concept_result = _update_concept_mastery(db, student_id, course_id, concept_id, topic_id, evidence, now)

    return {
        "topic":   topic_result,
        "concept": concept_result,
    }


# ---------------------------------------------------------------------------
# Topic mastery
# ---------------------------------------------------------------------------

def _update_topic_mastery(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: str,
    evidence: float,
    now: datetime,
) -> Dict[str, Any]:
    """Load or create LearnerTopicMastery, apply BKT, persist."""
    row = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id  == course_id,
        LearnerTopicMastery.topic_id   == topic_id,
    ).first()

    if row is None:
        row = LearnerTopicMastery(
            id=str(uuid.uuid4()).replace("-", ""),
            student_id=student_id,
            course_id=course_id,
            topic_id=topic_id,
            mastery_probability=BKT_INITIAL_MASTERY,
            attempt_count=0,
            correct_count=0,
            incorrect_count=0,
        )
        db.add(row)

    prior = float(row.mastery_probability or BKT_INITIAL_MASTERY)
    bkt_result = update_bkt_with_evidence(prior, evidence)

    row.mastery_probability = bkt_result["updated_mastery"]
    row.attempt_count   = (row.attempt_count or 0) + 1
    row.last_attempt_at = now
    row.updated_at      = now

    if evidence >= 0.5:
        row.correct_count = (row.correct_count or 0) + 1
        row.last_correct_at = now
    else:
        row.incorrect_count = (row.incorrect_count or 0) + 1
        row.last_incorrect_at = now

    db.commit()

    # Fetch topic name (gracefully handle deleted topics)
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    topic_name = topic.name if topic else "(deleted topic)"

    return {
        "id":              topic_id,
        "name":            topic_name,
        "prior_mastery":   round(prior, 4),
        "mastery":         round(float(row.mastery_probability), 4),
        "state":           classify_mastery(row.mastery_probability),
        "attempt_count":   row.attempt_count,
        "correct_count":   row.correct_count,
        "incorrect_count": row.incorrect_count,
        **bkt_result,
    }


# ---------------------------------------------------------------------------
# Concept mastery
# ---------------------------------------------------------------------------

def _update_concept_mastery(
    db: Session,
    student_id: str,
    course_id: str,
    concept_id: str,
    topic_id: Optional[str],
    evidence: float,
    now: datetime,
) -> Dict[str, Any]:
    """Load or create LearnerConceptMastery, apply BKT, persist."""
    row = db.query(LearnerConceptMastery).filter(
        LearnerConceptMastery.student_id  == student_id,
        LearnerConceptMastery.course_id   == course_id,
        LearnerConceptMastery.concept_id  == concept_id,
    ).first()

    if row is None:
        row = LearnerConceptMastery(
            id=str(uuid.uuid4()).replace("-", ""),
            student_id=student_id,
            course_id=course_id,
            concept_id=concept_id,
            topic_id=topic_id,
            mastery_probability=BKT_INITIAL_MASTERY,
            attempt_count=0,
            correct_count=0,
            incorrect_count=0,
        )
        db.add(row)

    prior = float(row.mastery_probability or BKT_INITIAL_MASTERY)
    bkt_result = update_bkt_with_evidence(prior, evidence)

    row.mastery_probability = bkt_result["updated_mastery"]
    row.attempt_count   = (row.attempt_count or 0) + 1
    row.last_attempt_at = now
    row.updated_at      = now

    if evidence >= 0.5:
        row.correct_count = (row.correct_count or 0) + 1
    else:
        row.incorrect_count = (row.incorrect_count or 0) + 1

    db.commit()

    # Fetch concept name
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    concept_name = concept.name if concept else "(deleted concept)"

    return {
        "id":              concept_id,
        "topic_id":        topic_id,
        "name":            concept_name,
        "prior_mastery":   round(prior, 4),
        "mastery":         round(float(row.mastery_probability), 4),
        "state":           classify_mastery(row.mastery_probability),
        "attempt_count":   row.attempt_count,
        "correct_count":   row.correct_count,
        "incorrect_count": row.incorrect_count,
        **bkt_result,
    }
