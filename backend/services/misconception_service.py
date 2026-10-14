"""
VIDYA-X AI — Misconception Orchestrator Service (Step 10)

Main orchestrator for detecting, validating, persisting, and managing the lifecycle
of student misconceptions.

Main entry point: detect_misconceptions()
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database.models import (
    QuizAttempt,
    Question,
    MisconceptionRecord,
    MisconceptionEvidence,
    Topic,
    Concept,
)
from services.search_service import semantic_search
from services.misconception_detection_service import (
    run_deterministic_checks,
    analyze_attempt_with_llm,
)


def detect_misconceptions(
    db: Session,
    student_id: str,
    course_id: str,
    attempt_id: str,
) -> Dict[str, Any]:
    """
    Perform diagnostic analysis on a student's quiz attempt (Section 4).

    Workflow:
      1. Load attempt & question
      2. Verify student & course isolation
      3. Idempotency check: skip if attempt was already analyzed
      4. Run fast deterministic checks
      5. If ambiguous, run grounded LLM analysis with course chunks
      6. Persist / update MisconceptionRecord & MisconceptionEvidence
      7. Return findings with confidence, status, and source citations
    """
    # 1. Load attempt
    attempt = db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()
    if not attempt:
        return {"error": f"Quiz attempt '{attempt_id}' not found"}

    # Security & isolation verification
    if student_id and attempt.student_id and attempt.student_id != student_id:
        return {"error": "Attempt does not belong to the specified student"}

    actual_student_id = attempt.student_id or student_id or "student_demo"

    # 2. Idempotency Check: check if evidence already exists for this attempt
    existing_evidence = db.query(MisconceptionEvidence).filter(
        MisconceptionEvidence.attempt_id == attempt_id
    ).all()
    if existing_evidence:
        findings = []
        for ev in existing_evidence:
            rec = db.query(MisconceptionRecord).filter(MisconceptionRecord.id == ev.misconception_id).first()
            if rec:
                findings.append(_serialize_misconception_record(db, rec))
        return {
            "status": "already_analyzed",
            "attempt_id": attempt_id,
            "student_id": actual_student_id,
            "course_id": course_id,
            "findings": findings,
        }

    # 3. Correct answer check (don't infer misconception for correct response without prior evidence)
    if attempt.is_correct == 1:
        # Check if this correct attempt helps resolve any active misconception for the concept
        _update_misconceptions_on_correct_attempt(db, actual_student_id, course_id, attempt.concept_id)
        return {
            "status": "no_misconception",
            "message": "Response is correct. No misconception detected.",
            "attempt_id": attempt_id,
            "findings": [],
        }

    # 4. Load question details
    q = db.query(Question).filter(Question.id == attempt.question_id).first()
    if not q:
        return {"error": f"Question '{attempt.question_id}' not found for attempt"}

    student_answer = attempt.student_answer or ""

    # 5. Deterministic Error Checks
    deterministic_result = run_deterministic_checks(
        question=q,
        student_answer=student_answer,
        is_correct=bool(attempt.is_correct),
        score=attempt.score or 0.0,
    )

    hypotheses = []
    if deterministic_result:
        hypotheses.append({
            "code": deterministic_result["code"],
            "title": deterministic_result["title"],
            "description": deterministic_result["description"],
            "confidence": deterministic_result["confidence"],
            "evidence": deterministic_result["evidence"],
            "resolved_source_refs": q.source_refs or [],
            "evidence_type": deterministic_result["evidence_type"],
        })
    else:
        # 6. Retrieve relevant course context & run LLM Analysis
        topic_query = ""
        if q.topic_id:
            t = db.query(Topic).filter(Topic.id == q.topic_id).first()
            if t:
                topic_query = t.name
        if not topic_query and q.concept_id:
            c = db.query(Concept).filter(Concept.id == q.concept_id).first()
            if c:
                topic_query = c.name
        if not topic_query:
            topic_query = q.prompt[:60]

        course_chunks = semantic_search(db=db, course_id=course_id, query=topic_query, top_k=4)

        llm_result = analyze_attempt_with_llm(
            db=db,
            question=q,
            student_answer=student_answer,
            attempt=attempt,
            course_context_chunks=course_chunks,
        )

        for h in llm_result.get("hypotheses", []):
            h["evidence_type"] = "llm_analysis"
            hypotheses.append(h)

    # 7. Persist or Update Misconception Records & Evidence
    saved_findings = []
    for h in hypotheses:
        rec = _upsert_misconception_record(
            db=db,
            student_id=actual_student_id,
            course_id=course_id,
            topic_id=q.topic_id,
            concept_id=q.concept_id,
            attempt_id=attempt_id,
            question_id=q.id,
            hypothesis=h,
            student_answer=student_answer,
            expected_answer=q.correct_answer,
        )
        saved_findings.append(_serialize_misconception_record(db, rec))

    return {
        "status": "success",
        "detected": len(saved_findings) > 0,
        "attempt_id": attempt_id,
        "student_id": actual_student_id,
        "course_id": course_id,
        "findings_count": len(saved_findings),
        "findings": saved_findings,
    }


def get_student_misconceptions(
    db: Session,
    student_id: str,
    course_id: str,
    status: Optional[str] = None,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve stored misconception records for a student in a course (Section 14).
    """
    query = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == student_id,
        MisconceptionRecord.course_id == course_id,
    )

    if status == "active":
        query = query.filter(MisconceptionRecord.status.in_(["suspected", "supported", "under_review", "improving"]))
    elif status:
        query = query.filter(MisconceptionRecord.status == status)
    if topic_id:
        query = query.filter(MisconceptionRecord.topic_id == topic_id)
    if concept_id:
        query = query.filter(MisconceptionRecord.concept_id == concept_id)

    records = query.order_by(MisconceptionRecord.last_observed_at.desc()).all()
    return [_serialize_misconception_record(db, r) for r in records]


def get_misconception_by_id(
    db: Session,
    misconception_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve single misconception detail view with confidence and evidence summaries.
    """
    rec = db.query(MisconceptionRecord).filter(MisconceptionRecord.id == misconception_id).first()
    if not rec:
        return None
    return _serialize_misconception_record(db, rec, include_evidence_details=True)


# ---------------------------------------------------------------------------
# Internal Helper Logic
# ---------------------------------------------------------------------------

def _upsert_misconception_record(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: Optional[str],
    concept_id: Optional[str],
    attempt_id: str,
    question_id: str,
    hypothesis: Dict[str, Any],
    student_answer: str,
    expected_answer: str,
) -> MisconceptionRecord:
    """
    Find existing MisconceptionRecord by (student_id, course_id, misconception_code) or create a new one.
    Updates confidence, occurrence count, and status conservatively (Section 8 & 12).
    """
    now = datetime.now(timezone.utc)
    code = hypothesis.get("code") or "conceptual_misunderstanding"

    rec = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == student_id,
        MisconceptionRecord.course_id == course_id,
        MisconceptionRecord.misconception_code == code,
    ).first()

    if rec:
        # Existing record: update occurrence & evidence
        rec.occurrence_count += 1
        rec.last_observed_at = now
        rec.updated_at = now

        # Conservative confidence rule: repeated evidence increases confidence
        rec.confidence = min(0.95, float(rec.confidence) + 0.15)

        # Status transition rule (Section 12)
        if rec.status == "suspected" and (rec.occurrence_count >= 2 or rec.confidence >= 0.70):
            rec.status = "supported"
        elif rec.status == "improving":
            rec.status = "under_review"

        db.commit()
    else:
        # New record creation
        rec_id = str(uuid.uuid4()).replace("-", "")
        init_confidence = float(hypothesis.get("confidence", 0.50))
        # Initial status rule
        init_status = "supported" if init_confidence >= 0.75 else "suspected"

        rec = MisconceptionRecord(
            id=rec_id,
            student_id=student_id,
            course_id=course_id,
            topic_id=topic_id,
            concept_id=concept_id,
            misconception_code=code,
            title=hypothesis.get("title") or "Identified Misconception Pattern",
            description=hypothesis.get("description") or "Observed pattern in quiz attempts.",
            evidence_summary="\n".join(hypothesis.get("evidence", [])),
            confidence=init_confidence,
            status=init_status,
            first_detected_at=now,
            last_observed_at=now,
            occurrence_count=1,
            created_at=now,
            updated_at=now,
        )
        db.add(rec)
        db.commit()

    # Create MisconceptionEvidence link (idempotent unique constraint)
    try:
        ev = MisconceptionEvidence(
            id=str(uuid.uuid4()).replace("-", ""),
            misconception_id=rec.id,
            attempt_id=attempt_id,
            question_id=question_id,
            student_answer_summary=student_answer[:255] if student_answer else "",
            expected_answer_summary=expected_answer[:255] if expected_answer else "",
            evidence_type=hypothesis.get("evidence_type", "llm_analysis"),
            evidence_strength=hypothesis.get("confidence", 0.50),
            created_at=now,
        )
        db.add(ev)
        db.commit()
    except IntegrityError:
        db.rollback()  # Evidence link already existed

    return rec


def calculate_misconception_confidence(occurrence_count: int, base_confidence: float = 0.50) -> tuple[float, str]:
    """
    Calculate updated confidence and status progression:
    - 1 occurrence -> suspected (or supported if base_confidence >= 0.75)
    - 2+ occurrences -> supported
    - Capped at 0.95 maximum confidence
    """
    conf = min(0.95, base_confidence + (occurrence_count - 1) * 0.15)
    status = "supported" if (occurrence_count >= 2 or conf >= 0.75) else "suspected"
    return (round(conf, 2), status)


def _update_misconceptions_on_correct_attempt(
    db: Session,
    student_id: str,
    course_id: str,
    concept_id: Optional[str],
):
    """
    When student answers a question correctly for a concept, move active misconceptions
    for that concept to 'improving' or 'under_review' (Section 12).
    """
    if not concept_id:
        return

    active_recs = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == student_id,
        MisconceptionRecord.course_id == course_id,
        MisconceptionRecord.concept_id == concept_id,
        MisconceptionRecord.status.in_(["suspected", "supported", "under_review"]),
    ).all()

    now = datetime.now(timezone.utc)
    for r in active_recs:
        if r.status in ("suspected", "supported"):
            r.status = "improving"
        elif r.status == "improving" and r.occurrence_count <= 2:
            r.status = "resolved"
            r.resolved_at = now
        r.updated_at = now

    if active_recs:
        db.commit()


def _serialize_misconception_record(
    db: Session,
    rec: MisconceptionRecord,
    include_evidence_details: bool = False,
) -> Dict[str, Any]:
    """Format MisconceptionRecord for API JSON responses."""
    topic_name = "General"
    concept_name = "General"

    if rec.topic_id:
        t = db.query(Topic).filter(Topic.id == rec.topic_id).first()
        if t:
            topic_name = t.name
    if rec.concept_id:
        c = db.query(Concept).filter(Concept.id == rec.concept_id).first()
        if c:
            concept_name = c.name

    data = {
        "id": rec.id,
        "student_id": rec.student_id,
        "course_id": rec.course_id,
        "topic_id": rec.topic_id,
        "topic_name": topic_name,
        "concept_id": rec.concept_id,
        "concept_name": concept_name,
        "misconception_code": rec.misconception_code,
        "title": rec.title,
        "description": rec.description,
        "evidence_summary": rec.evidence_summary,
        "confidence": round(float(rec.confidence or 0.50), 2),
        "status": rec.status,
        "occurrence_count": rec.occurrence_count,
        "first_detected_at": rec.first_detected_at.isoformat() if rec.first_detected_at else None,
        "last_observed_at": rec.last_observed_at.isoformat() if rec.last_observed_at else None,
        "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
    }

    if include_evidence_details:
        ev_rows = db.query(MisconceptionEvidence).filter(MisconceptionEvidence.misconception_id == rec.id).all()
        data["evidence_list"] = [
            {
                "id": ev.id,
                "attempt_id": ev.attempt_id,
                "question_id": ev.question_id,
                "student_answer": ev.student_answer_summary,
                "expected_answer": ev.expected_answer_summary,
                "evidence_type": ev.evidence_type,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in ev_rows
        ]

    return data
