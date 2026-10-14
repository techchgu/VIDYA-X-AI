"""
VIDYA-X AI — Topic Prioritization Engine Service (Step 12)

Calculates deterministic priority scores for course topics based on:
  - BKT mastery need (30%)
  - Recent error signal (20%)
  - Active supported misconceptions (15%)
  - Foundational prerequisite need (15%)
  - Due flashcards review signal (10%)
  - Exam proximity relevance (10%)
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    Topic,
    Concept,
    Prerequisite,
    LearnerTopicMastery,
    LearnerConceptMastery,
    QuizAttempt,
    MisconceptionRecord,
    Flashcard,
    FlashcardDeck,
)

logger = logging.getLogger(__name__)

# Configurable Priority Weights
WEIGHT_MASTERY_NEED = 0.30
WEIGHT_RECENT_ERROR = 0.20
WEIGHT_MISCONCEPTION = 0.15
WEIGHT_PREREQUISITE_NEED = 0.15
WEIGHT_REVIEW_DUE = 0.10
WEIGHT_EXAM_RELEVANCE = 0.10


def calculate_topic_priorities(
    db: Session,
    student_id: str,
    course_id: str,
    exam_date: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate prioritized scores and reasons for all topics in a course.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Fetch all course topics
    topics = db.query(Topic).filter(Topic.course_id == course_id).order_by(Topic.order_index.asc()).all()
    if not topics:
        return []

    # 2. Pre-fetch BKT topic masteries
    bkt_rows = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == student_id,
        LearnerTopicMastery.course_id == course_id,
    ).all()
    bkt_map = {b.topic_id: b for b in bkt_rows if b.topic_id}

    # 3. Pre-fetch active misconceptions
    active_statuses = ["suspected", "supported", "under_review", "improving"]
    misc_rows = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == student_id,
        MisconceptionRecord.course_id == course_id,
        MisconceptionRecord.status.in_(active_statuses),
    ).all()
    misc_map = {}
    for m in misc_rows:
        if m.topic_id:
            misc_map[m.topic_id] = m

    # 4. Pre-fetch due flashcards per topic
    due_cards_rows = (
        db.query(Flashcard)
        .join(FlashcardDeck, Flashcard.deck_id == FlashcardDeck.id)
        .filter(
            FlashcardDeck.student_id == student_id,
            FlashcardDeck.course_id == course_id,
        )
        .all()
    )
    due_cards_count_map = {}
    for c in due_cards_rows:
        is_due = (c.next_review_at is None) or (c.next_review_at <= now)
        if is_due and c.topic_id:
            due_cards_count_map[c.topic_id] = due_cards_count_map.get(c.topic_id, 0) + 1

    # 5. Pre-fetch prerequisites in course
    prereqs = db.query(Prerequisite).filter(Prerequisite.course_id == course_id).all()
    # Build concept to topic map
    concepts = db.query(Concept).join(Topic, Concept.topic_id == Topic.id).filter(Topic.course_id == course_id).all()
    concept_to_topic = {c.id: c.topic_id for c in concepts}
    topic_prereq_topics = {}  # topic_id -> list of prereq_topic_ids
    for p in prereqs:
        p_top = concept_to_topic.get(p.prerequisite_concept_id)
        t_top = concept_to_topic.get(p.target_concept_id)
        if p_top and t_top and p_top != t_top:
            if t_top not in topic_prereq_topics:
                topic_prereq_topics[t_top] = set()
            topic_prereq_topics[t_top].add(p_top)

    # 6. Calculate exam proximity weight
    exam_rel = 0.30
    days_to_exam = None
    if exam_date:
        if exam_date.tzinfo is None:
            exam_date = exam_date.replace(tzinfo=timezone.utc)
        days_to_exam = (exam_date - now).days
        if days_to_exam <= 7:
            exam_rel = 1.0
        elif days_to_exam <= 14:
            exam_rel = 0.80
        elif days_to_exam <= 30:
            exam_rel = 0.50
        else:
            exam_rel = 0.20

    # 7. Evaluate each topic
    prioritized_list = []
    cutoff_7d = now - timedelta(days=7)

    for topic in topics:
        # A. Mastery Signal
        bkt = bkt_map.get(topic.id)
        if bkt and bkt.attempt_count > 0:
            mastery_val = bkt.mastery_probability
            if mastery_val < 0.50:
                mastery_need = min(1.0, 1.5 * (1.0 - mastery_val))
            else:
                mastery_need = max(0.0, 1.0 - mastery_val)
            has_history = True
        else:
            mastery_val = 0.20  # default cold start
            mastery_need = 0.80
            has_history = False

        # B. Recent Error Signal
        recent_attempts = (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.student_id == student_id,
                QuizAttempt.topic_id == topic.id,
                QuizAttempt.submitted_at >= cutoff_7d,
            )
            .all()
        )
        if recent_attempts:
            wrong_count = sum(1 for a in recent_attempts if a.is_correct == 0)
            error_signal = wrong_count / float(len(recent_attempts))
        else:
            error_signal = 0.0

        # C. Misconception Signal
        misc = misc_map.get(topic.id)
        if misc:
            if misc.status in ["supported", "under_review"]:
                misc_signal = 1.0
            elif misc.status == "improving":
                misc_signal = 0.50
            else:
                misc_signal = 0.75
        else:
            misc_signal = 0.0

        # D. Prerequisite Need Signal
        prereq_top_ids = topic_prereq_topics.get(topic.id, set())
        prereq_need = 0.0
        weak_prereq_names = []
        for p_top_id in prereq_top_ids:
            p_bkt = bkt_map.get(p_top_id)
            p_mastery = p_bkt.mastery_probability if (p_bkt and p_bkt.attempt_count > 0) else 0.20
            if p_mastery < 0.50:
                p_need = 1.0 - p_mastery
                if p_need > prereq_need:
                    prereq_need = p_need
                p_t_obj = db.query(Topic).filter(Topic.id == p_top_id).first()
                if p_t_obj:
                    weak_prereq_names.append(p_t_obj.name)

        # E. Due Flashcards Signal
        due_count = due_cards_count_map.get(topic.id, 0)
        review_due_signal = min(1.0, due_count / 5.0)

        # F. Priority Score Formula
        score = (
            (WEIGHT_MASTERY_NEED * mastery_need)
            + (WEIGHT_RECENT_ERROR * error_signal)
            + (WEIGHT_MISCONCEPTION * misc_signal)
            + (WEIGHT_PREREQUISITE_NEED * prereq_need)
            + (WEIGHT_REVIEW_DUE * review_due_signal)
            + (WEIGHT_EXAM_RELEVANCE * exam_rel)
        )
        score = max(0.0, min(1.0, round(score, 3)))

        # Priority Level
        if score >= 0.60:
            level = "high"
        elif score >= 0.35:
            level = "medium"
        else:
            level = "low"

        # Construct Human-Readable Reason
        reasons = []
        if misc:
            reasons.append(f"Active misconception: '{misc.title}'")
        if weak_prereq_names:
            reasons.append(f"Prerequisite review required ({', '.join(weak_prereq_names)})")
        if error_signal > 0.3:
            reasons.append(f"Recent quiz errors ({int(error_signal * 100)}% error rate)")
        if due_count > 0:
            reasons.append(f"{due_count} due flashcard reviews")
        if mastery_need >= 0.50:
            reasons.append(f"Mastery opportunity ({int(mastery_val * 100)}% BKT mastery)")
        if days_to_exam is not None and days_to_exam <= 14:
            reasons.append(f"Exam in {days_to_exam} days")

        if not reasons:
            reasons.append("Standard review topic")

        reason_str = " • ".join(reasons)

        prioritized_list.append({
            "topic_id": topic.id,
            "topic_name": topic.name,
            "priority_score": score,
            "priority_level": level,
            "priority_reason": reason_str,
            "mastery_probability": round(mastery_val, 2),
            "has_history": has_history,
            "active_misconception": misc.title if misc else None,
            "due_flashcard_count": due_count,
            "prerequisite_need": round(prereq_need, 2),
            "weak_prerequisites": weak_prereq_names,
            "recent_error_rate": round(error_signal, 2),
        })

    # Sort descending by priority_score
    prioritized_list.sort(key=lambda x: x["priority_score"], reverse=True)
    return prioritized_list
