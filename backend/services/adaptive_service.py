"""
VIDYA-X AI — Adaptive Engine Orchestrator Service (Step 9)

Main orchestration layer for Step 9 adaptive question selection.
Builds on top of Step 7 question generation/verification and Step 8 BKT learner model.

Main entry point: get_next_question()
"""

import uuid
import random
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from database.models import (
    Question,
    QuizSession,
    QuizQuestion,
    QuizAttempt,
    LearnerTopicMastery,
    LearnerConceptMastery,
    Topic,
    Concept,
    AdaptiveLog,
)
from services.mastery_service import (
    has_learner_history,
    get_all_mastery,
    get_concept_mastery_list,
)
from services.candidate_service import (
    get_candidate_questions,
    get_recently_used_questions,
    filter_and_relax_candidates,
    get_recent_attempts_history,
)
from services.adaptive_scoring_service import (
    score_question_candidate,
    calculate_target_difficulty,
    ADAPTIVE_WEAK_THRESHOLD,
    ADAPTIVE_DEVELOPING_THRESHOLD,
    ADAPTIVE_MASTERED_THRESHOLD,
    ADAPTIVE_MASTERED_TOPIC_PROBABILITY,
)
from services.question_service import _serialize_question, store_question
from services.question_generation_service import generate_questions
from services.question_verification_service import verify_question


def get_next_question(
    db: Session,
    student_id: str,
    course_id: str,
    current_quiz_id: Optional[str] = None,
    preferred_question_type: Optional[str] = None,
    target_topic_id: Optional[str] = None,
    target_concept_id: Optional[str] = None,
    force_selection: bool = False,
) -> Dict[str, Any]:
    """
    Select the most useful next question for the student based on BKT learner model state,
    prerequisites, difficulty fit, recent performance, novelty, and diversity.

    Args:
        db:                      SQLAlchemy session.
        student_id:              Student identifier.
        course_id:               Course identifier.
        current_quiz_id:         Optional active quiz session ID.
        preferred_question_type: Optional specific question type (mcq, short_answer, numerical).
        target_topic_id:         Optional specific topic focus.
        target_concept_id:       Optional specific concept focus.
        force_selection:         If True, bypasses cold_start check to return a question.

    Returns:
        Structured response dictionary containing selected question_id, topic, concept, difficulty,
        reason, mastery estimate, and question payload (without answer fields).
    """
    # 1. Cold-start check (Step 36)
    if not force_selection and not target_topic_id and not target_concept_id:
        if not has_learner_history(db, student_id, course_id):
            return {
                "status": "cold_start",
                "message": "Complete the diagnostic to enable personalized practice.",
                "diagnostic_available": True,
            }

    # 2. Fetch Learner State (BKT topic and concept masteries)
    topic_rows = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id == course_id,
    ).all()
    topic_mastery_map = {r.topic_id: float(r.mastery_probability) for r in topic_rows if r.topic_id}

    concept_rows = db.query(LearnerConceptMastery).filter(
        LearnerConceptMastery.student_id == student_id,
        LearnerConceptMastery.course_id == course_id,
    ).all()
    concept_mastery_map = {r.concept_id: float(r.mastery_probability) for r in concept_rows if r.concept_id}

    # 3. Determine target topic/concept if not specified
    if not target_topic_id and not target_concept_id:
        target_topic_id, target_concept_id = _select_target_focus(
            db, course_id, topic_mastery_map, concept_mastery_map
        )

    # 4. Fetch candidate questions & recently used history
    raw_candidates = get_candidate_questions(
        db=db,
        student_id=student_id,
        course_id=course_id,
        topic_id=target_topic_id,
        concept_id=target_concept_id,
        limit=50,
    )

    recently_used_ids = get_recently_used_questions(db, student_id, course_id, window_hours=72)
    candidate_questions = filter_and_relax_candidates(raw_candidates, recently_used_ids, min_candidates=3)

    # 5. Fetch attempt history for recency, failure, and question type diversity
    recent_attempts = get_recent_attempts_history(db, student_id, course_id, limit=20)
    
    # Calculate attempt counts per question
    attempt_counts: Dict[str, int] = {}
    for att in recent_attempts:
        if att.question_id:
            attempt_counts[att.question_id] = attempt_counts.get(att.question_id, 0) + 1

    recent_types = [a.question_type for a in recent_attempts if a.question_type]

    # Filter candidates by preferred_question_type if requested and available
    if preferred_question_type:
        matching_type = [q for q in candidate_questions if q.question_type == preferred_question_type]
        if matching_type:
            candidate_questions = matching_type

    # 6. Score candidate questions
    scored_candidates = []
    for q in candidate_questions:
        scored = score_question_candidate(
            db=db,
            question=q,
            student_id=student_id,
            course_id=course_id,
            concept_mastery_map=concept_mastery_map,
            topic_mastery_map=topic_mastery_map,
            recent_attempts=recent_attempts,
            attempt_counts=attempt_counts,
            recent_question_types=recent_types,
        )
        scored_candidates.append(scored)

    # Sort candidates by total score descending
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    # 7. Select best question or execute Fallback Strategy (Step 37)
    selected_scored = None
    if scored_candidates:
        selected_scored = scored_candidates[0]
    else:
        # Fallback sequence: generate a new grounded question
        generated_q = _fallback_generate_question(
            db=db,
            course_id=course_id,
            student_id=student_id,
            target_topic_id=target_topic_id,
            target_concept_id=target_concept_id,
            concept_mastery_map=concept_mastery_map,
            recently_used_ids=recently_used_ids,
        )
        if generated_q:
            selected_scored = score_question_candidate(
                db=db,
                question=generated_q,
                student_id=student_id,
                course_id=course_id,
                concept_mastery_map=concept_mastery_map,
                topic_mastery_map=topic_mastery_map,
                recent_attempts=recent_attempts,
                attempt_counts=attempt_counts,
                recent_question_types=recent_types,
            )

    if not selected_scored:
        return {
            "error": "No suitable question could be selected or generated for this course.",
            "status": "no_questions",
        }

    q = selected_scored["question"]
    reason = selected_scored["reason"]
    mastery_val = selected_scored["mastery"]
    score_val = selected_scored["score"]

    # 8. Log decision in AdaptiveLog for evaluation metrics (Step 53 & 54)
    _log_adaptive_decision(
        db=db,
        student_id=student_id,
        course_id=course_id,
        quiz_id=current_quiz_id,
        question_id=q.id,
        topic_id=q.topic_id,
        concept_id=q.concept_id,
        mastery_before=mastery_val,
        selected_difficulty=q.difficulty,
        question_type=q.question_type,
        selection_reason=reason,
        adaptive_score=score_val,
    )

    # 9. Format response payload (without exposing internal scores or answer fields to student)
    return {
        "status": "success",
        "question_id": q.id,
        "topic_id": q.topic_id,
        "concept_id": q.concept_id,
        "difficulty": q.difficulty,
        "question_type": q.question_type,
        "reason": reason,
        "mastery": mastery_val,
        "question": _serialize_question(q, include_answer=False),
    }


def create_adaptive_quiz(
    db: Session,
    student_id: str,
    course_id: str,
    count: int = 10,
    question_types: Optional[List[str]] = None,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new adaptive quiz session (POST /api/adaptive/quiz).
    """
    session_id = str(uuid.uuid4()).replace("-", "")
    session = QuizSession(
        id=session_id,
        course_id=course_id,
        student_id=student_id,
        title=f"AI Adaptive Practice — {datetime.now(timezone.utc).strftime('%b %d, %H:%M')}",
        mode="adaptive",
        adaptive=1,
        current_question_index=0,
    )
    db.add(session)
    db.commit()

    # Retrieve initial question for this session
    first_q_res = get_next_question(
        db=db,
        student_id=student_id,
        course_id=course_id,
        current_quiz_id=session_id,
        preferred_question_type=question_types[0] if question_types else None,
        target_topic_id=topic_id,
        target_concept_id=concept_id,
        force_selection=True,
    )

    questions_list = []
    if first_q_res.get("status") == "success" and "question" in first_q_res:
        q_obj = first_q_res["question"]
        q_obj["selection_reason"] = first_q_res["reason"]
        q_obj["estimated_mastery"] = first_q_res["mastery"]
        questions_list.append(q_obj)

        # Record in QuizQuestion join table
        db.add(QuizQuestion(
            id=str(uuid.uuid4()).replace("-", ""),
            quiz_session_id=session_id,
            question_id=first_q_res["question_id"],
            order_index=0,
        ))
        db.commit()

    return {
        "quiz_id": session_id,
        "adaptive": True,
        "total_requested": count,
        "questions": questions_list,
    }


def get_adaptive_next_question_for_session(
    db: Session,
    quiz_id: str,
    student_id: str,
    course_id: str,
) -> Dict[str, Any]:
    """
    Fetch the next adaptive question for an ongoing adaptive quiz session (GET /api/adaptive/next-question).
    Reads the latest BKT learner state after recent answer submissions.
    """
    session = db.query(QuizSession).filter(QuizSession.id == quiz_id).first()
    if not session:
        return {"error": f"Quiz session '{quiz_id}' not found"}

    next_res = get_next_question(
        db=db,
        student_id=student_id or session.student_id or "default_student",
        course_id=course_id or session.course_id,
        current_quiz_id=quiz_id,
        force_selection=True,
    )

    if next_res.get("status") == "success" and "question_id" in next_res:
        q_id = next_res["question_id"]
        # Attach question to QuizQuestion if not already present
        existing_link = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_session_id == quiz_id,
            QuizQuestion.question_id == q_id,
        ).first()

        if not existing_link:
            idx = db.query(QuizQuestion).filter(QuizQuestion.quiz_session_id == quiz_id).count()
            db.add(QuizQuestion(
                id=str(uuid.uuid4()).replace("-", ""),
                quiz_session_id=quiz_id,
                question_id=q_id,
                order_index=idx,
            ))
            session.current_question_index = idx
            db.commit()

    return next_res


# ---------------------------------------------------------------------------
# Helper logic
# ---------------------------------------------------------------------------

def _select_target_focus(
    db: Session,
    course_id: str,
    topic_mastery_map: Dict[str, float],
    concept_mastery_map: Dict[str, float],
) -> tuple[Optional[str], Optional[str]]:
    """
    Select target topic & concept prioritizing:
      Priority 1 — Weak concepts (mastery < 0.50)
      Priority 2 — Developing concepts (0.50 <= mastery < 0.80)
      Priority 3 — Prerequisites
      Priority 4 — Mastered concepts (10% exploration probability)
    """
    # Exploration roll (10% chance to pick mastered topic for retention review)
    if topic_mastery_map and random.random() < ADAPTIVE_MASTERED_TOPIC_PROBABILITY:
        mastered_topics = [tid for tid, m in topic_mastery_map.items() if m >= ADAPTIVE_MASTERED_THRESHOLD]
        if mastered_topics:
            return random.choice(mastered_topics), None

    # Priority 1: Weak concepts (< 0.50)
    weak_concepts = [cid for cid, m in concept_mastery_map.items() if m < ADAPTIVE_WEAK_THRESHOLD]
    if weak_concepts:
        chosen_c = random.choice(weak_concepts)
        c_obj = db.query(Concept).filter(Concept.id == chosen_c).first()
        return (c_obj.topic_id if c_obj else None), chosen_c

    # Priority 2: Developing concepts (0.50 <= mastery < 0.80)
    dev_concepts = [cid for cid, m in concept_mastery_map.items() if ADAPTIVE_WEAK_THRESHOLD <= m < ADAPTIVE_DEVELOPING_THRESHOLD]
    if dev_concepts:
        chosen_c = random.choice(dev_concepts)
        c_obj = db.query(Concept).filter(Concept.id == chosen_c).first()
        return (c_obj.topic_id if c_obj else None), chosen_c

    # Weak topics (< 0.50)
    weak_topics = [tid for tid, m in topic_mastery_map.items() if m < ADAPTIVE_WEAK_THRESHOLD]
    if weak_topics:
        return random.choice(weak_topics), None

    # Default fallback to any topic in course
    course_topics = db.query(Topic.id).filter(Topic.course_id == course_id).all()
    if course_topics:
        return random.choice([t[0] for t in course_topics]), None

    return None, None


def _fallback_generate_question(
    db: Session,
    course_id: str,
    student_id: str,
    target_topic_id: Optional[str],
    target_concept_id: Optional[str],
    concept_mastery_map: Dict[str, float],
    recently_used_ids: set,
) -> Optional[Question]:
    """
    Fallback Sequence (Step 37): Generate a new grounded question from course materials.
    """
    topic_name = "General"
    if target_topic_id:
        t = db.query(Topic).filter(Topic.id == target_topic_id).first()
        if t:
            topic_name = t.name
    elif target_concept_id:
        c = db.query(Concept).filter(Concept.id == target_concept_id).first()
        if c:
            topic_name = c.name

    mastery = concept_mastery_map.get(target_concept_id or "", 0.20)
    target_diff = calculate_target_difficulty(mastery)
    if "-" in target_diff:
        target_diff = target_diff.split("-")[0]

    try:
        new_qs = generate_questions(
            db=db,
            course_id=course_id,
            topic_query=topic_name,
            question_types=["mcq", "short_answer"],
            count=3,
            difficulty=target_diff,
        )
        for qdict in new_qs:
            q = db.query(Question).filter(Question.id == qdict["id"]).first()
            if q and q.id not in recently_used_ids:
                return q
    except Exception as exc:
        print(f"[ADAPTIVE] Fallback question generation failed: {exc}")

    return None


def _log_adaptive_decision(
    db: Session,
    student_id: str,
    course_id: str,
    quiz_id: Optional[str],
    question_id: str,
    topic_id: Optional[str],
    concept_id: Optional[str],
    mastery_before: float,
    selected_difficulty: str,
    question_type: str,
    selection_reason: str,
    adaptive_score: float,
):
    """Persist decision record into AdaptiveLog table."""
    try:
        log_entry = AdaptiveLog(
            id=str(uuid.uuid4()).replace("-", ""),
            student_id=student_id,
            course_id=course_id,
            quiz_id=quiz_id,
            question_id=question_id,
            topic_id=topic_id,
            concept_id=concept_id,
            mastery_before=mastery_before,
            selected_difficulty=selected_difficulty,
            question_type=question_type,
            selection_reason=selection_reason,
            adaptive_score=adaptive_score,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        db.commit()
    except Exception as exc:
        print(f"[ADAPTIVE LOG ERROR] {exc}")
