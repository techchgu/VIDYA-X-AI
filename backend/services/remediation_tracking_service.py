"""
VIDYA-X AI — Remediation Tracking & Outcome Evaluation Service (Step 10)

Tracks student remediation session completion and evaluates post-remediation outcomes
cautiously based on assessment evidence (Section 13).
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    RemediationSession,
    RemediationActivity,
    MisconceptionRecord,
    QuizAttempt,
)
from services.mastery_service import get_concept_mastery


def get_remediation_session(
    db: Session,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve full detail of a single remediation session with activities."""
    session = db.query(RemediationSession).filter(RemediationSession.id == session_id).first()
    if not session:
        return None
    return _serialize_remediation_session(db, session)


def get_student_remediations(
    db: Session,
    student_id: str,
    course_id: str,
) -> List[Dict[str, Any]]:
    """List all remediation sessions for a student in a course."""
    sessions = db.query(RemediationSession).filter(
        RemediationSession.student_id == student_id,
        RemediationSession.course_id == course_id,
    ).order_by(RemediationSession.created_at.desc()).all()

    return [_serialize_remediation_session(db, s) for s in sessions]


def complete_remediation_activity(
    db: Session,
    session_id: str,
    activity_id: Optional[str],
    student_id: str,
) -> Dict[str, Any]:
    """
    Mark an activity (or the entire remediation session) as completed.
    Validates student ownership (Section 14 & 21).
    """
    session = db.query(RemediationSession).filter(RemediationSession.id == session_id).first()
    if not session:
        return {"error": f"Remediation session '{session_id}' not found"}

    if session.student_id != student_id:
        return {"error": "Remediation session does not belong to the specified student"}

    now = datetime.now(timezone.utc)

    if activity_id:
        act = db.query(RemediationActivity).filter(
            RemediationActivity.id == activity_id,
            RemediationActivity.remediation_session_id == session_id,
        ).first()
        if act:
            act.completed_at = now
            db.commit()

    # Check if all activities in session are finished
    incomplete_count = db.query(RemediationActivity).filter(
        RemediationActivity.remediation_session_id == session_id,
        RemediationActivity.completed_at.is_(None),
    ).count()

    if incomplete_count == 0:
        session.status = "completed"
        session.completed_at = now
        db.commit()

        # Update associated misconception status to 'under_review' if supported
        if session.misconception_id:
            m_rec = db.query(MisconceptionRecord).filter(MisconceptionRecord.id == session.misconception_id).first()
            if m_rec and m_rec.status in ("suspected", "supported"):
                m_rec.status = "under_review"
                m_rec.updated_at = now
                db.commit()

    return _serialize_remediation_session(db, session)


def evaluate_remediation_outcome(
    db: Session,
    student_id: str,
    course_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Evaluate post-remediation assessment evidence for a remediation session (Section 13).

    Returns cautious, observational outcome indicators without overstating causality.
    """
    session = db.query(RemediationSession).filter(RemediationSession.id == session_id).first()
    if not session:
        return {"error": f"Remediation session '{session_id}' not found"}

    if session.student_id != student_id:
        return {"error": "Session ownership validation failed"}

    created_at = session.created_at

    # Retrieve attempts for this concept before and after remediation creation
    attempts_query = db.query(QuizAttempt).filter(
        QuizAttempt.student_id == student_id,
    )
    if session.concept_id:
        attempts_query = attempts_query.filter(QuizAttempt.concept_id == session.concept_id)

    all_attempts = attempts_query.order_by(QuizAttempt.submitted_at.asc()).all()

    pre_attempts = [a for a in all_attempts if a.submitted_at and a.submitted_at < created_at]
    post_attempts = [a for a in all_attempts if a.submitted_at and a.submitted_at >= created_at]

    pre_correct = sum(1 for a in pre_attempts if a.is_correct == 1)
    pre_total = len(pre_attempts)
    pre_pct = round((pre_correct / pre_total * 100), 1) if pre_total > 0 else None

    post_correct = sum(1 for a in post_attempts if a.is_correct == 1)
    post_total = len(post_attempts)
    post_pct = round((post_correct / post_total * 100), 1) if post_total > 0 else None

    # Fetch current BKT mastery
    bkt_data = get_concept_mastery(db, student_id, course_id, session.concept_id) if session.concept_id else None
    current_mastery = bkt_data.get("mastery") if bkt_data else None

    # Outcome Status Classification (Section 13)
    if post_total < 2:
        outcome_status = "Insufficient evidence to determine improvement"
        outcome_detail = "Complete more practice questions to evaluate post-remediation progress."
    elif post_pct is not None and pre_pct is not None and post_pct > pre_pct:
        outcome_status = "Improvement observed"
        outcome_detail = f"Assessment accuracy increased from {pre_pct}% before remediation to {post_pct}% after remediation."
    elif post_pct is not None and post_pct >= 75.0:
        outcome_status = "Improvement observed"
        outcome_detail = f"Post-remediation assessment accuracy is {post_pct}%."
    else:
        outcome_status = "Further practice recommended"
        outcome_detail = f"Post-remediation accuracy is {post_pct}%. Additional targeted practice is recommended."

    return {
        "session_id": session_id,
        "student_id": student_id,
        "course_id": course_id,
        "concept_id": session.concept_id,
        "misconception_id": session.misconception_id,
        "pre_remediation_attempts": pre_total,
        "pre_remediation_accuracy": pre_pct,
        "post_remediation_attempts": post_total,
        "post_remediation_accuracy": post_pct,
        "current_bkt_mastery": current_mastery,
        "outcome_status": outcome_status,
        "outcome_detail": outcome_detail,
        "disclaimer": "Observational evidence based on assessment history, not controlled causality.",
    }


def _serialize_remediation_session(
    db: Session,
    session: RemediationSession,
) -> Dict[str, Any]:
    """Serialize RemediationSession ORM model to JSON dict."""
    activities = db.query(RemediationActivity).filter(
        RemediationActivity.remediation_session_id == session.id
    ).order_by(RemediationActivity.order_index.asc()).all()

    return {
        "session_id": session.id,
        "student_id": session.student_id,
        "course_id": session.course_id,
        "topic_id": session.topic_id,
        "concept_id": session.concept_id,
        "misconception_id": session.misconception_id,
        "session_type": session.session_type,
        "status": session.status,
        "explanation": session.explanation,
        "source_refs": session.source_refs or [],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "activities": [
            {
                "activity_id": a.id,
                "activity_type": a.activity_type,
                "activity_data": a.activity_data,
                "order_index": a.order_index,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in activities
        ],
    }
