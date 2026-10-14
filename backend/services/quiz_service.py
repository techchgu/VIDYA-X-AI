"""
VIDYA-X AI — Quiz Session Service (Step 7)
Manages quiz session lifecycle: creation, retrieval, answer submission, and results.

Security note:
  - GET /api/quiz/{quiz_id}     → NEVER exposes correct_answer / is_correct / solution
  - GET /api/quiz/{quiz_id}/result → exposes answers only AFTER the quiz is evaluated
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from database.models import (
    Question,
    QuestionOption,
    QuizSession,
    QuizQuestion,
    QuizAttempt,
    QuestionUsage,
)
from services.question_service import (
    get_question_by_id,
    record_question_result,
    _serialize_question,
)


# ---------------------------------------------------------------------------
# Quiz creation
# ---------------------------------------------------------------------------

def create_quiz(
    db: Session,
    course_id: str,
    question_ids: List[str],
    title: Optional[str] = None,
    mode: str = "practice",
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new quiz session from a list of pre-generated question IDs.

    Args:
        db: SQLAlchemy session.
        course_id: Course the quiz belongs to.
        question_ids: Ordered list of question IDs to include.
        title: Human-readable quiz title.
        mode: 'practice' or 'exam'.
        student_id: Optional student identifier for usage tracking.

    Returns:
        Quiz session dict including the question list (without answers).
    """
    session_id = str(uuid.uuid4()).replace("-", "")
    session = QuizSession(
        id=session_id,
        course_id=course_id,
        title=title or f"Quiz — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        mode=mode,
    )
    db.add(session)

    # Attach questions
    for idx, q_id in enumerate(question_ids):
        db.add(QuizQuestion(
            id=str(uuid.uuid4()).replace("-", ""),
            quiz_session_id=session_id,
            question_id=q_id,
            order_index=idx,
        ))
        # Track usage
        if student_id:
            db.add(QuestionUsage(
                id=str(uuid.uuid4()).replace("-", ""),
                question_id=q_id,
                student_id=student_id,
            ))

    db.commit()
    db.refresh(session)

    return _serialize_session(db, session, include_answers=False)


# ---------------------------------------------------------------------------
# Quiz retrieval (no answers exposed)
# ---------------------------------------------------------------------------

def get_quiz(db: Session, quiz_id: str) -> Optional[Dict[str, Any]]:
    """
    Return quiz session data with questions but WITHOUT correct answers.
    This is the safe payload sent to the quiz UI.
    """
    session = db.query(QuizSession).filter(QuizSession.id == quiz_id).first()
    if not session:
        return None
    return _serialize_session(db, session, include_answers=False)


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------

def submit_answer(
    db: Session,
    quiz_id: str,
    question_id: str,
    student_answer: str,
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate a student's answer for one question and persist the attempt.

    Returns:
        Dict with is_correct, score, feedback, explanation, and source_refs.
    """
    # Check session exists
    session = db.query(QuizSession).filter(QuizSession.id == quiz_id).first()
    if not session:
        return {"error": f"Quiz session '{quiz_id}' not found"}

    # Fetch question WITH answer for evaluation
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        return {"error": f"Question '{question_id}' not found"}

    # Check the question belongs to this quiz
    link = db.query(QuizQuestion).filter(
        QuizQuestion.quiz_session_id == quiz_id,
        QuizQuestion.question_id == question_id,
    ).first()
    if not link:
        return {"error": "Question does not belong to this quiz session"}

    # Evaluate answer
    is_correct, score, feedback = _evaluate_answer(q, student_answer)

    # Persist attempt
    attempt_id = record_question_result(
        db=db,
        quiz_session_id=quiz_id,
        question_id=question_id,
        student_answer=student_answer,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        student_id=student_id,
        topic_id=q.topic_id,
        concept_id=q.concept_id,
        question_type=q.question_type,
        difficulty=q.difficulty,
    )

    # Step 3: Update BKT learner model (only AFTER verified evaluation)
    mastery_update = None
    if student_id and session.course_id:
        try:
            from services.learner_model_service import update_learner_after_attempt
            mastery_update = update_learner_after_attempt(
                db=db,
                student_id=student_id,
                course_id=session.course_id,
                question_id=question_id,
                is_correct=is_correct,
                score=score,
            )
        except Exception:
            mastery_update = None

    # Step 10: Trigger Misconception Analysis (safely caught so evaluation never fails)
    misconception_analysis = None
    if student_id and session.course_id and attempt_id:
        try:
            from services.misconception_service import detect_misconceptions
            misconception_analysis = detect_misconceptions(
                db=db,
                student_id=student_id,
                course_id=session.course_id,
                attempt_id=attempt_id,
            )
        except Exception as exc:
            misconception_analysis = None

    # Return immediate feedback (always expose answer AFTER submission)
    return {
        "attempt_id":     attempt_id,
        "question_id":    question_id,
        "student_answer": student_answer,
        "is_correct":     is_correct,
        "score":          score,
        "feedback":       feedback,
        "correct_answer": q.correct_answer,
        "explanation":    q.explanation or "",
        "source_refs":    q.source_refs or [],
        **({"solution": q.solution} if q.question_type == "numerical" and q.solution else {}),
        "mastery_update": mastery_update,
        "misconception_analysis": misconception_analysis,
    }



# ---------------------------------------------------------------------------
# Quiz results
# ---------------------------------------------------------------------------

def get_quiz_result(db: Session, quiz_id: str) -> Optional[Dict[str, Any]]:
    """
    Return complete quiz results including per-question breakdowns with answers.
    """
    session = db.query(QuizSession).filter(QuizSession.id == quiz_id).first()
    if not session:
        return None

    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_session_id == quiz_id)
        .all()
    )

    # Build attempt map keyed by question_id (last attempt wins if multiple)
    attempt_map: Dict[str, QuizAttempt] = {}
    for a in attempts:
        attempt_map[a.question_id] = a

    # Ordered quiz questions
    quiz_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_session_id == quiz_id)
        .order_by(QuizQuestion.order_index)
        .all()
    )

    total = len(quiz_questions)
    correct = 0
    question_results = []

    for qq in quiz_questions:
        q = qq.question
        attempt = attempt_map.get(q.id)
        answered = attempt is not None
        q_correct = bool(attempt.is_correct) if answered else False
        if q_correct:
            correct += 1

        q_data = _serialize_question(q, include_answer=True)
        q_data["student_answer"] = attempt.student_answer if answered else None
        q_data["is_correct"] = q_correct if answered else None
        q_data["score"] = float(attempt.score) if answered and attempt.score is not None else None
        q_data["feedback"] = attempt.feedback if answered else "Not attempted"
        question_results.append(q_data)

    score_pct = round((correct / total) * 100, 1) if total > 0 else 0.0

    return {
        "quiz_id": quiz_id,
        "title": session.title,
        "mode": session.mode,
        "total_questions": total,
        "answered": len(attempt_map),
        "correct": correct,
        "score_percent": score_pct,
        "grade": _grade(score_pct),
        "questions": question_results,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _evaluate_answer(q: Question, student_answer: str) -> tuple:
    """
    Evaluate student_answer against q.correct_answer.

    Returns:
        (is_correct: bool, score: float, feedback: str)
    """
    correct = (q.correct_answer or "").strip()
    answer = (student_answer or "").strip()

    if q.question_type == "mcq":
        is_correct = answer.upper() == correct.upper()
        score = 1.0 if is_correct else 0.0
        feedback = "Correct!" if is_correct else f"Incorrect. The correct answer is option {correct}."
        return is_correct, score, feedback

    if q.question_type == "numerical":
        # Flexible numeric comparison with tolerance
        try:
            student_val = float(re.sub(r"[^\d\.\-\+eE]", "", answer))
            correct_val = float(re.sub(r"[^\d\.\-\+eE]", "", correct))
            tolerance = abs(correct_val) * 0.01 if correct_val != 0 else 0.01
            is_correct = abs(student_val - correct_val) <= tolerance
            score = 1.0 if is_correct else 0.0
            feedback = "Correct!" if is_correct else f"Incorrect. The expected value is {correct}."
        except (ValueError, TypeError):
            # Treat as text match if numeric parsing fails
            is_correct = answer.lower() == correct.lower()
            score = 1.0 if is_correct else 0.0
            feedback = "Correct!" if is_correct else f"Incorrect. Expected: {correct}"
        return is_correct, score, feedback

    # short_answer: partial-credit scoring based on keyword overlap
    correct_words = set(re.findall(r"\w+", correct.lower()))
    answer_words = set(re.findall(r"\w+", answer.lower()))
    if not correct_words:
        return False, 0.0, "Could not evaluate answer."
    overlap = len(correct_words & answer_words) / len(correct_words)
    is_correct = overlap >= 0.5
    score = round(min(overlap, 1.0), 2)
    if overlap >= 0.8:
        feedback = "Excellent! Your answer closely matches the source material."
    elif overlap >= 0.5:
        feedback = "Partially correct. Review the source material for a complete answer."
    else:
        feedback = f"Incorrect. Key concepts missing. Reference answer: {correct[:200]}"
    return is_correct, score, feedback


def _grade(score_pct: float) -> str:
    if score_pct >= 90:
        return "A"
    if score_pct >= 75:
        return "B"
    if score_pct >= 60:
        return "C"
    if score_pct >= 40:
        return "D"
    return "F"


def _serialize_session(db: Session, session: QuizSession, include_answers: bool) -> Dict[str, Any]:
    """Serialize a QuizSession ORM object to a dict."""
    quiz_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_session_id == session.id)
        .order_by(QuizQuestion.order_index)
        .all()
    )
    questions = [
        _serialize_question(qq.question, include_answer=include_answers)
        for qq in quiz_questions
    ]
    return {
        "quiz_id": session.id,
        "course_id": session.course_id,
        "title": session.title,
        "mode": session.mode,
        "total_questions": len(questions),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "questions": questions,
    }


# Resolve local import cycle
import re  # noqa: E402
