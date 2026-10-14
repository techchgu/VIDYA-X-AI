"""
VIDYA-X AI — Personalization Service (Step 9)

Provides high-level personalized recommendations and study plans for the user dashboard
and future study planner based on BKT learner model state.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import Topic, Concept, LearnerTopicMastery, LearnerConceptMastery
from services.mastery_service import (
    has_learner_history,
    get_all_mastery,
    get_concept_mastery_list,
)
from services.adaptive_scoring_service import (
    calculate_target_difficulty,
    ADAPTIVE_WEAK_THRESHOLD,
    ADAPTIVE_DEVELOPING_THRESHOLD,
)


def get_personalized_recommendations(
    db: Session,
    student_id: str,
    course_id: str,
) -> Dict[str, Any]:
    """
    Generate high-level personalized recommendations for a student in a course.

    Endpoint: GET /api/personalization/{student_id}/course/{course_id}
    """
    if not has_learner_history(db, student_id, course_id):
        return {
            "student_id": student_id,
            "course_id": course_id,
            "has_history": False,
            "message": "Complete a few questions first. Your personalized recommendations will appear here.",
            "recommended_topics": [],
            "recommended_difficulty": "medium",
            "recommended_question_types": ["mcq", "short_answer"],
        }

    mastery_summary = get_all_mastery(db, student_id, course_id)
    overall_mastery = mastery_summary.get("overall_mastery") or 0.50

    topics = mastery_summary.get("topics", [])

    # Sort topics by mastery ascending (weakest first)
    sorted_topics = sorted(topics, key=lambda t: t.get("mastery", 0.20))

    recommended_topics = []
    for t in sorted_topics:
        m = t.get("mastery", 0.20)
        if m < ADAPTIVE_WEAK_THRESHOLD:
            reason = "Needs additional practice"
        elif m < ADAPTIVE_DEVELOPING_THRESHOLD:
            reason = "Developing"
        else:
            reason = "Mastered — maintenance review"

        recommended_topics.append({
            "topic_id": t.get("topic_id"),
            "topic_name": t.get("topic_name"),
            "mastery": t.get("mastery"),
            "reason": reason,
        })

    # Recommended difficulty based on overall learner mastery
    rec_diff = calculate_target_difficulty(overall_mastery)

    # Determine recommended question types based on weak area needs
    rec_types = ["mcq", "short_answer"]
    if overall_mastery < 0.40:
        rec_types = ["mcq"]
    elif overall_mastery >= 0.70:
        rec_types = ["numerical", "short_answer"]

    return {
        "student_id": student_id,
        "course_id": course_id,
        "has_history": True,
        "overall_mastery": overall_mastery,
        "recommended_topics": recommended_topics,
        "recommended_difficulty": rec_diff,
        "recommended_question_types": rec_types,
    }
