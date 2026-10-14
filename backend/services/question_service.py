"""
VIDYA-X AI — Question Store Service (Step 7)
Handles fingerprinting, deduplication, storage, and retrieval of generated questions.
All questions MUST be grounded in course material chunks — no invented facts.
"""

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from database.models import Question, QuestionOption, QuizAttempt


# ---------------------------------------------------------------------------
# Fingerprinting helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """
    Normalize question prompt for deduplication comparison.
    Lowercases, strips punctuation, collapses whitespace.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_fingerprint(prompt: str) -> str:
    """Return a 64-character SHA-256 hex digest of the normalized prompt."""
    normalized = _normalize_text(prompt)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def question_exists(db: Session, fingerprint: str) -> bool:
    """Return True if a question with this fingerprint already exists in the DB."""
    return db.query(Question).filter(Question.fingerprint == fingerprint).first() is not None


def store_question(db: Session, question_data: Dict[str, Any]) -> str:
    """
    Persist a single verified question (and its MCQ options) to the database.
    Silently skips if the fingerprint already exists.

    Args:
        db: SQLAlchemy session.
        question_data: dict with keys matching Question model fields.

    Returns:
        question id (new or existing).
    """
    fingerprint = question_data.get("fingerprint") or compute_fingerprint(question_data["prompt"])

    # Deduplication guard
    existing = db.query(Question).filter(Question.fingerprint == fingerprint).first()
    if existing:
        return existing.id

    q_id = str(uuid.uuid4()).replace("-", "")

    question = Question(
        id=q_id,
        course_id=question_data["course_id"],
        topic_id=question_data.get("topic_id"),
        concept_id=question_data.get("concept_id"),
        question_type=question_data["question_type"],
        prompt=question_data["prompt"],
        difficulty=question_data.get("difficulty", "medium"),
        correct_answer=question_data["correct_answer"],
        explanation=question_data.get("explanation", ""),
        solution=question_data.get("solution"),
        source_refs=question_data.get("source_refs", []),
        fingerprint=fingerprint,
        status="active",
    )
    db.add(question)

    # Store MCQ options if present
    for opt in question_data.get("options", []):
        db.add(QuestionOption(
            id=str(uuid.uuid4()).replace("-", ""),
            question_id=q_id,
            option_key=opt["key"],
            option_text=opt["text"],
            is_correct=1 if opt.get("is_correct") else 0,
        ))

    db.commit()
    db.refresh(question)
    return q_id


def get_question_by_id(db: Session, question_id: str, include_answer: bool = False) -> Optional[Dict[str, Any]]:
    """
    Retrieve a question dict by ID.

    Args:
        db: SQLAlchemy session.
        question_id: Question primary key.
        include_answer: If False, correct_answer / solution / is_correct are omitted.

    Returns:
        Dict representation or None.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        return None
    return _serialize_question(q, include_answer=include_answer)


def get_questions_for_course(
    db: Session,
    course_id: str,
    topic_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Retrieve active questions for a course, with optional filters (no answers)."""
    q = db.query(Question).filter(
        Question.course_id == course_id,
        Question.status == "active",
    )
    if topic_id:
        q = q.filter(Question.topic_id == topic_id)
    if question_type:
        q = q.filter(Question.question_type == question_type)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    rows = q.limit(limit).all()
    return [_serialize_question(r, include_answer=False) for r in rows]


def record_question_result(
    db: Session,
    quiz_session_id: str,
    question_id: str,
    student_answer: str,
    is_correct: bool,
    score: float,
    feedback: str,
    student_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> str:
    """Persist a quiz attempt row and return its ID."""
    attempt_id = str(uuid.uuid4()).replace("-", "")
    attempt = QuizAttempt(
        id=attempt_id,
        quiz_session_id=quiz_session_id,
        question_id=question_id,
        student_id=student_id,
        topic_id=topic_id,
        concept_id=concept_id,
        question_type=question_type,
        difficulty=difficulty,
        student_answer=student_answer,
        is_correct=1 if is_correct else 0,
        score=score,
        feedback=feedback,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()
    return attempt_id


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------

def _serialize_question(q: Question, include_answer: bool = False) -> Dict[str, Any]:
    """Convert a Question ORM object to a plain dict suitable for JSON serialization."""
    data: Dict[str, Any] = {
        "id": q.id,
        "question_type": q.question_type,
        "prompt": q.prompt,
        "difficulty": q.difficulty,
        "source_refs": q.source_refs or [],
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }

    if q.question_type == "mcq":
        data["options"] = [
            {
                "key": opt.option_key,
                "text": opt.option_text,
                **({"is_correct": bool(opt.is_correct)} if include_answer else {}),
            }
            for opt in sorted(q.options, key=lambda o: o.option_key)
        ]

    if include_answer:
        data["correct_answer"] = q.correct_answer
        data["explanation"] = q.explanation
        if q.question_type == "numerical" and q.solution:
            data["solution"] = q.solution

    return data
