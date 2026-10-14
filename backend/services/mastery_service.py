"""
VIDYA-X AI — Mastery Summary Service (Step 8)
Reads, summarizes, and exposes topic/concept mastery for API responses.
Designed to be consumed by Step 9 adaptive question selection.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import (
    LearnerTopicMastery,
    LearnerConceptMastery,
    Topic,
    Concept,
)
from services.bkt_service import classify_mastery, WEAK_TOPIC_THRESHOLD, MASTERY_THRESHOLD


# ---------------------------------------------------------------------------
# Public API for Step 9
# ---------------------------------------------------------------------------

def get_topic_mastery(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: str,
) -> Optional[Dict[str, Any]]:
    """Return mastery data for a single topic. Returns None if no history."""
    row = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id  == course_id,
        LearnerTopicMastery.topic_id   == topic_id,
    ).first()
    if not row:
        return None
    return _serialize_topic_mastery(db, row)


def get_concept_mastery(
    db: Session,
    student_id: str,
    course_id: str,
    concept_id: str,
) -> Optional[Dict[str, Any]]:
    """Return mastery data for a single concept. Returns None if no history."""
    row = db.query(LearnerConceptMastery).filter(
        LearnerConceptMastery.student_id  == student_id,
        LearnerConceptMastery.course_id   == course_id,
        LearnerConceptMastery.concept_id  == concept_id,
    ).first()
    if not row:
        return None
    return _serialize_concept_mastery(db, row)


def get_all_mastery(
    db: Session,
    student_id: str,
    course_id: str,
) -> Dict[str, Any]:
    """
    Return full learner mastery summary for a student in a course.
    Overall mastery = mean of topic-level mastery probabilities.
    Students with NO attempts will receive overall_mastery=None (not 0%).
    """
    topic_rows = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id  == course_id,
    ).all()

    topics = [_serialize_topic_mastery(db, r) for r in topic_rows]

    if not topics:
        overall = None
    else:
        overall = round(sum(t["mastery"] for t in topics) / len(topics), 4)

    return {
        "student_id":      student_id,
        "course_id":       course_id,
        "overall_mastery": overall,
        "topics":          topics,
        "has_history":     len(topics) > 0,
    }


def get_weak_topics(
    db: Session,
    student_id: str,
    course_id: str,
) -> List[Dict[str, Any]]:
    """Return topics below WEAK_TOPIC_THRESHOLD."""
    rows = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id           == student_id,
        LearnerTopicMastery.course_id            == course_id,
        LearnerTopicMastery.mastery_probability  <  WEAK_TOPIC_THRESHOLD,
    ).all()
    result = []
    for row in rows:
        d = _serialize_topic_mastery(db, row)
        d["reason"] = "Low estimated mastery based on recent assessment performance"
        result.append(d)
    return result


def get_strong_topics(
    db: Session,
    student_id: str,
    course_id: str,
) -> List[Dict[str, Any]]:
    """Return topics at or above MASTERY_THRESHOLD."""
    rows = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id           == student_id,
        LearnerTopicMastery.course_id            == course_id,
        LearnerTopicMastery.mastery_probability  >= MASTERY_THRESHOLD,
    ).all()
    return [_serialize_topic_mastery(db, row) for row in rows]


def get_concept_mastery_list(
    db: Session,
    student_id: str,
    course_id: str,
) -> List[Dict[str, Any]]:
    """Return all concept mastery records for a student in a course."""
    rows = db.query(LearnerConceptMastery).filter(
        LearnerConceptMastery.student_id == student_id,
        LearnerConceptMastery.course_id  == course_id,
    ).all()
    return [_serialize_concept_mastery(db, r) for r in rows]


def reset_learner_state(
    db: Session,
    student_id: str,
    course_id: str,
) -> Dict[str, Any]:
    """
    Delete all learner mastery records for a student in a course.
    Does NOT delete uploaded materials, questions, or quiz sessions.
    """
    topics_deleted = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id  == course_id,
    ).delete(synchronize_session="fetch")

    concepts_deleted = db.query(LearnerConceptMastery).filter(
        LearnerConceptMastery.student_id == student_id,
        LearnerConceptMastery.course_id  == course_id,
    ).delete(synchronize_session="fetch")

    db.commit()
    return {
        "student_id":        student_id,
        "course_id":         course_id,
        "topics_deleted":    topics_deleted,
        "concepts_deleted":  concepts_deleted,
        "reset_at":          datetime.now(timezone.utc).isoformat(),
    }


def has_learner_history(
    db: Session,
    student_id: str,
    course_id: str,
) -> bool:
    """Return True if the student has any mastery records for this course."""
    return db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id  == course_id,
    ).first() is not None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_topic_mastery(db: Session, row: LearnerTopicMastery) -> Dict[str, Any]:
    topic = db.query(Topic).filter(Topic.id == row.topic_id).first()
    topic_name = topic.name if topic else "(deleted topic)"
    return {
        "topic_id":        row.topic_id,
        "topic_name":      topic_name,
        "mastery":         round(float(row.mastery_probability or 0.0), 4),
        "state":           classify_mastery(row.mastery_probability or 0.0),
        "attempt_count":   row.attempt_count or 0,
        "correct_count":   row.correct_count or 0,
        "incorrect_count": row.incorrect_count or 0,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "last_correct_at": row.last_correct_at.isoformat() if row.last_correct_at else None,
        "last_incorrect_at": row.last_incorrect_at.isoformat() if row.last_incorrect_at else None,
        "updated_at":      row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_concept_mastery(db: Session, row: LearnerConceptMastery) -> Dict[str, Any]:
    concept = db.query(Concept).filter(Concept.id == row.concept_id).first()
    concept_name = concept.name if concept else "(deleted concept)"
    return {
        "concept_id":      row.concept_id,
        "topic_id":        row.topic_id,
        "concept_name":    concept_name,
        "mastery":         round(float(row.mastery_probability or 0.0), 4),
        "state":           classify_mastery(row.mastery_probability or 0.0),
        "attempt_count":   row.attempt_count or 0,
        "correct_count":   row.correct_count or 0,
        "incorrect_count": row.incorrect_count or 0,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "updated_at":      row.updated_at.isoformat() if row.updated_at else None,
    }
