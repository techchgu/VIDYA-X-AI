"""
VIDYA-X AI — Revision Personalization Service (Step 11)

Analyzes learner BKT mastery history, recorded misconceptions, and topic preferences
to generate personalized emphasis rules and personalization metadata for revision resources.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import Topic, Concept, MisconceptionRecord
from services.mastery_service import get_all_mastery, has_learner_history
from services.misconception_service import get_student_misconceptions


def build_personalization_plan(
    db: Session,
    student_id: str,
    course_id: str,
    requested_topic_id: Optional[str] = None,
    material_type: str = "revision_notes",
) -> Dict[str, Any]:
    """
    Build a personalization strategy combining BKT mastery levels and active misconceptions.
    Does NOT replace requested topic if provided; instead tailors emphasis within the requested topic.
    """
    has_history = has_learner_history(db, student_id, course_id)
    reasons = []
    emphasis_rules = []
    misconception_callouts = []
    weak_topic_names = []

    if not has_history:
        reasons.append("New student profile without prior quiz history. Generating balanced introductory revision resource.")
        return {
            "mode": "balanced_introductory",
            "has_history": False,
            "reasons": reasons,
            "emphasis_rules": ["Provide balanced coverage of foundational definitions and core concepts."],
            "misconception_callouts": [],
            "weak_topics": [],
        }

    # Retrieve learner mastery summary
    mastery_data = get_all_mastery(db, student_id, course_id)
    topics_mastery = mastery_data.get("topics", [])

    weak_topics = [t for t in topics_mastery if t.get("mastery", 1.0) < 0.50]
    developing_topics = [t for t in topics_mastery if 0.50 <= t.get("mastery", 1.0) < 0.80]
    mastered_topics = [t for t in topics_mastery if t.get("mastery", 1.0) >= 0.80]

    for wt in weak_topics:
        weak_topic_names.append(wt.get("topic_name", "Unknown Topic"))

    # Fetch active misconceptions
    active_misconceptions = get_student_misconceptions(db, student_id, course_id, status="active")
    for m in active_misconceptions[:3]:
        misconception_callouts.append({
            "code": m.get("misconception_code"),
            "title": m.get("title"),
            "description": m.get("description"),
            "topic_name": m.get("topic_name"),
        })

    # Mode determination
    if requested_topic_id:
        target_topic = db.query(Topic).filter(Topic.id == requested_topic_id, Topic.course_id == course_id).first()
        topic_name = target_topic.name if target_topic else "Selected Topic"
        mode = "topic_focused"
        reasons.append(f"Student explicitly selected focus topic: '{topic_name}'.")

        # Find mastery for this specific topic
        target_mastery_obj = next((t for t in topics_mastery if t.get("topic_id") == requested_topic_id), None)
        if target_mastery_obj:
            m_val = target_mastery_obj.get("mastery", 0.50)
            if m_val < 0.50:
                reasons.append(f"Recorded mastery for '{topic_name}' is low ({int(m_val*100)}%). Emphasizing foundational concepts and step-by-step examples.")
                emphasis_rules.append("Emphasize basic definitions, core steps, and clear visual/text explanations.")
            elif m_val < 0.80:
                reasons.append(f"Recorded mastery for '{topic_name}' is developing ({int(m_val*100)}%). Including core formulas and concept comparisons.")
                emphasis_rules.append("Focus on core relations, formula applications, and self-check prompts.")
            else:
                reasons.append(f"Recorded mastery for '{topic_name}' is high ({int(m_val*100)}%). Prioritizing concise exam-style summaries.")
                emphasis_rules.append("Keep explanations concise, focusing on key distinctions and quick recall.")
        else:
            emphasis_rules.append("Provide standard balanced breakdown of core concepts.")
    else:
        if weak_topics:
            mode = "weak_topic_review"
            reasons.append(f"Identified {len(weak_topics)} weak topic(s) requiring targeted review ({', '.join(weak_topic_names[:2])}).")
            emphasis_rules.append("Prioritize weak topics, addressing foundational gaps and providing extra worked examples.")
        elif developing_topics:
            mode = "mastery_enhancement"
            reasons.append(f"Student has developing mastery across {len(developing_topics)} topic(s).")
            emphasis_rules.append("Focus on deepening understanding, concept comparisons, and key distinctions.")
        else:
            mode = "advanced_review"
            reasons.append("High overall mastery demonstrated across completed topics.")
            emphasis_rules.append("Prioritize quick exam review, key definitions, and cross-concept summaries.")

    if misconception_callouts:
        reasons.append(f"Incorporating corrective notes for {len(misconception_callouts)} recorded student misconception(s).")
        emphasis_rules.append("Explicitly contrast common mistaken approaches with authoritative course methods.")

    return {
        "mode": mode,
        "has_history": True,
        "reasons": reasons,
        "emphasis_rules": emphasis_rules,
        "misconception_callouts": misconception_callouts,
        "weak_topics": weak_topic_names,
    }
