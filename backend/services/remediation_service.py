"""
VIDYA-X AI — Personalized Remediation Service (Step 10)

Generates personalized, source-grounded corrective teaching sessions and activities
addressing observed student misconceptions or weak concepts.

Reuses existing Grounded RAG (search_service) and Question Generation (question_generation_service).
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from database.models import (
    Topic,
    Concept,
    Prerequisite,
    MisconceptionRecord,
    RemediationSession,
    RemediationActivity,
)
from services.search_service import semantic_search
from services.mastery_service import get_concept_mastery, get_topic_mastery
from services.question_generation_service import generate_questions
from services.llm_service import _call_gemini_api

logger = logging.getLogger(__name__)


def create_remediation(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
    misconception_id: Optional[str] = None,
    preferred_language: str = "English",
) -> Dict[str, Any]:
    """
    Create a personalized remediation session with grounded explanations,
    contrast comparisons, worked examples, self-checks, and practice questions (Section 10 & 11).
    """
    # 1. Load misconception record if provided
    misconception = None
    if misconception_id:
        misconception = db.query(MisconceptionRecord).filter(MisconceptionRecord.id == misconception_id).first()
        if misconception:
            topic_id = topic_id or misconception.topic_id
            concept_id = concept_id or misconception.concept_id

    # Resolve topic & concept names
    topic_name = "General"
    concept_name = "General"
    if topic_id:
        t = db.query(Topic).filter(Topic.id == topic_id).first()
        if t:
            topic_name = t.name
    if concept_id:
        c = db.query(Concept).filter(Concept.id == concept_id).first()
        if c:
            concept_name = c.name

    # 2. Check Learner BKT State & Prerequisite Mastery (Section 11)
    prereq_note = None
    if concept_id:
        prereqs = db.query(Prerequisite).filter(
            Prerequisite.course_id == course_id,
            Prerequisite.target_concept_id == concept_id,
        ).all()
        for p in prereqs:
            p_mastery = get_concept_mastery(db, student_id, course_id, p.prerequisite_concept_id)
            p_val = p_mastery.get("mastery", 0.20) if p_mastery else 0.20
            if p_val < 0.50:
                p_concept = db.query(Concept).filter(Concept.id == p.prerequisite_concept_id).first()
                p_name = p_concept.name if p_concept else "prerequisite concept"
                prereq_note = f"Note: Your estimated mastery of foundational prerequisite '{p_name}' is currently low ({int(p_val*100)}%). Reviewing the prerequisite concept first will make this material easier to master."
                break

    # 3. Retrieve Grounded Course Chunks via Semantic Search
    query = f"{topic_name} {concept_name}"
    if misconception:
        query += f" {misconception.title}"

    chunks = semantic_search(db=db, course_id=course_id, query=query, top_k=4)

    source_refs = []
    chunk_context = ""
    for idx, ch in enumerate(chunks):
        s_id = f"SOURCE_{idx+1}"
        m = ch.get("chunk_metadata") or {}
        ref_entry = {
            "chunk_id": ch.get("id"),
            "file_name": ch.get("file_name", "Course Material"),
            "page": m.get("page"),
            "slide": m.get("slide"),
            "timestamp_start": m.get("timestamp_start"),
        }
        source_refs.append(ref_entry)
        chunk_context += f"\n[{s_id}] {ref_entry['file_name']}: {ch.get('content', '')}\n"

    # 4. Generate Grounded Remediation Payload with LLM
    remediation_content = _generate_remediation_content(
        topic_name=topic_name,
        concept_name=concept_name,
        misconception=misconception,
        chunk_context=chunk_context,
        prereq_note=prereq_note,
        preferred_language=preferred_language,
    )

    # 5. Generate Targeted Practice Question reusing existing Question Generator
    practice_question = None
    try:
        new_qs = generate_questions(
            db=db,
            course_id=course_id,
            topic_query=f"{topic_name} {concept_name}",
            question_types=["mcq", "short_answer"],
            count=1,
            difficulty="medium",
        )
        if new_qs:
            practice_question = new_qs[0]
    except Exception as exc:
        logger.warning(f"[REMEDIATION PRACTICE Q FAIL] {exc}")

    # 6. Create & Persist RemediationSession
    session_id = str(uuid.uuid4()).replace("-", "")
    rem_session = RemediationSession(
        id=session_id,
        student_id=student_id,
        course_id=course_id,
        topic_id=topic_id,
        concept_id=concept_id,
        misconception_id=misconception_id,
        session_type="targeted_remediation",
        status="active",
        explanation=remediation_content.get("corrective_explanation", "Targeted concept review."),
        source_refs=source_refs,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rem_session)

    # 7. Create RemediationActivities
    activities_list = [
        {
            "activity_type": "comparison",
            "order_index": 1,
            "activity_data": {
                "mistaken_approach": remediation_content.get("mistaken_approach", "Interchanging concepts without accounting for relationships."),
                "correct_approach": remediation_content.get("correct_approach", "Applying the exact definitions and equations from course material."),
                "key_takeaway": remediation_content.get("key_takeaway", "Focus on fundamental definitions."),
            }
        },
        {
            "activity_type": "worked_example",
            "order_index": 2,
            "activity_data": {
                "problem": remediation_content.get("worked_example_problem", f"Example application in {concept_name}."),
                "solution_steps": remediation_content.get("worked_example_steps", ["Identify given variables.", "Apply formula.", "Calculate answer."]),
            }
        },
        {
            "activity_type": "self_check",
            "order_index": 3,
            "activity_data": {
                "question": remediation_content.get("self_check_prompt", f"What is the key principle of {concept_name}?"),
                "options": remediation_content.get("self_check_options", ["Option A", "Option B"]),
                "correct_option_index": 0,
                "explanation": remediation_content.get("self_check_explanation", "Correct based on course definition."),
            }
        }
    ]

    if practice_question:
        activities_list.append({
            "activity_type": "practice_question",
            "order_index": 4,
            "activity_data": {
                "question_id": practice_question.get("id"),
                "prompt": practice_question.get("prompt"),
                "question_type": practice_question.get("question_type"),
                "options": practice_question.get("options", []),
            }
        })

    for act in activities_list:
        db.add(RemediationActivity(
            id=str(uuid.uuid4()).replace("-", ""),
            remediation_session_id=session_id,
            activity_type=act["activity_type"],
            activity_data=act["activity_data"],
            order_index=act["order_index"],
        ))

    db.commit()

    return {
        "session_id": session_id,
        "student_id": student_id,
        "course_id": course_id,
        "topic_name": topic_name,
        "concept_name": concept_name,
        "misconception_title": misconception.title if misconception else None,
        "prereq_note": prereq_note,
        "corrective_explanation": remediation_content.get("corrective_explanation"),
        "correct_concept_summary": remediation_content.get("correct_concept_summary"),
        "source_refs": source_refs,
        "activities": activities_list,
        "created_at": rem_session.created_at.isoformat(),
    }


def _generate_remediation_content(
    topic_name: str,
    concept_name: str,
    misconception: Optional[MisconceptionRecord],
    chunk_context: str,
    prereq_note: Optional[str],
    preferred_language: str,
) -> Dict[str, Any]:
    """Use LLM with grounded course context to format structured remediation explanation."""

    lang_instr = f"Respond in {preferred_language} language." if preferred_language in ("Hindi", "Hinglish") else "Respond in clear English."

    sys_instruction = (
        "You are an empathetic, precise AI tutor on VIDYA-X AI. "
        "Create a clear, concise remediation explanation for a student based strictly on course context.\n\n"
        "STRICT RULES:\n"
        "1. Base all conceptual claims strictly on the provided course material.\n"
        "2. Do NOT invent unsupported facts or formulas.\n"
        "3. Keep explanations short, supportive, and focused.\n"
        "4. Return strictly valid JSON.\n"
    )

    prompt = f"""{sys_instruction}
{lang_instr}

TOPIC: {topic_name}
CONCEPT: {concept_name}
{f"SUSPECTED MISCONCEPTION: {misconception.title} - {misconception.description}" if misconception else ""}
{f"PREREQUISITE NOTICE: {prereq_note}" if prereq_note else ""}

COURSE MATERIAL CONTEXT:
{chunk_context or "No specific course chunks retrieved."}

Output a JSON object with this exact structure:
{{
  "corrective_explanation": "Concise 2-3 sentence corrective explanation of the concept.",
  "correct_concept_summary": "Core definition or formula to remember.",
  "mistaken_approach": "Brief description of the mistaken concept or approach.",
  "correct_approach": "Step-by-step correct conceptual approach.",
  "key_takeaway": "Single key rule to avoid this error.",
  "worked_example_problem": "A simple worked problem scenario testing this concept.",
  "worked_example_steps": ["Step 1...", "Step 2...", "Final answer..."],
  "self_check_prompt": "Quick self-check question prompt for the student.",
  "self_check_options": ["Correct option statement", "Incorrect distractor statement"],
  "self_check_explanation": "Explanation of why option A is correct."
}}
"""

    try:
        raw_resp = _call_gemini_api(prompt, system_instruction=sys_instruction, temperature=0.2)
        clean_text = raw_resp.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(clean_text)
    except Exception as exc:
        logger.warning(f"[REMEDIATION GENERATION FALLBACK] {exc}")
        return {
            "corrective_explanation": f"Let's review the fundamental principles of {concept_name}.",
            "correct_concept_summary": f"Focus on the authoritative course definitions for {concept_name}.",
            "mistaken_approach": "Confusing related physical quantities or variable substitutions.",
            "correct_approach": "Apply the standard formula and verify unit dimensions.",
            "key_takeaway": "Double-check units and initial variable definitions before calculating.",
            "worked_example_problem": f"Apply the definition of {concept_name} step-by-step.",
            "worked_example_steps": ["Identify given values", "Substitute into formula", "Calculate result"],
            "self_check_prompt": f"What is the key principle of {concept_name}?",
            "self_check_options": [f"Standard definition of {concept_name}", "Interchanged variable concept"],
            "self_check_explanation": "Always refer back to the course definitions.",
        }
