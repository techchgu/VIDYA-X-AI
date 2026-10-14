"""
VIDYA-X AI — Revision Service Orchestrator (Step 11)

Main orchestrator for generating, validating, persisting, retrieving, listing,
and deleting revision resources and flashcard decks.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    Course,
    Topic,
    KnowledgeChunk,
    RevisionMaterial,
    RevisionMaterialSource,
    FlashcardDeck,
)
from services.search_service import semantic_search
from services.revision_validation_service import (
    validate_topic_and_course,
    extract_source_map_from_chunks,
    resolve_and_validate_citations,
)
from services.revision_personalization_service import build_personalization_plan
from services.revision_generation_service import generate_revision_content


def generate_revision_material(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: Optional[str] = None,
    material_type: str = "revision_notes",
    language: str = "English",
    depth: str = "standard",
) -> Dict[str, Any]:
    """
    Generate, validate, and persist a personalized, grounded revision resource.
    """
    # 1. Validate course existence
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course '{course_id}' not found."}

    # 2. Validate topic ownership
    valid_topic, err_msg = validate_topic_and_course(db, course_id, topic_id=topic_id)
    if not valid_topic:
        return {"error": err_msg}

    # Resolve topic name
    topic_name = "General Course Overview"
    if topic_id:
        t = db.query(Topic).filter(Topic.id == topic_id).first()
        if t:
            topic_name = t.name

    # 3. Retrieve RAG chunks
    query_str = f"{topic_name} core definitions concepts principles"
    chunks = semantic_search(db=db, course_id=course_id, query=query_str, top_k=6)

    if not chunks:
        # Check if course has any chunks at all
        total_chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.course_id == course_id).count()
        if total_chunks == 0:
            return {
                "error": f"No course materials uploaded for '{course.name}'. Upload materials first to generate grounded revision resources.",
                "insufficient_materials": True,
            }

    source_map, context_text = extract_source_map_from_chunks(chunks)

    # 4. Build Personalization Strategy
    personalization = build_personalization_plan(
        db, student_id, course_id, requested_topic_id=topic_id, material_type=material_type
    )

    # 5. Generate Content via LLM / Fallback
    content_json = generate_revision_content(
        course_name=course.name,
        topic_name=topic_name,
        material_type=material_type,
        language=language,
        depth=depth,
        context_text=context_text,
        source_map=source_map,
        personalization=personalization,
    )

    # 6. Resolve Citations & Validate Grounding
    all_raw_citations = []
    for sec in content_json.get("sections", []):
        all_raw_citations.extend(sec.get("citations", []))
    for sc in content_json.get("self_check", []):
        all_raw_citations.extend(sc.get("citations", []))

    resolved_cits, verified_sources = resolve_and_validate_citations(all_raw_citations, source_map)
    is_grounded = len(chunks) > 0 and (len(verified_sources) > 0 or len(chunks) > 0)

    # 7. Persist RevisionMaterial & RevisionMaterialSource
    now = datetime.now(timezone.utc)
    mat_id = str(uuid.uuid4()).replace("-", "")

    mat = RevisionMaterial(
        id=mat_id,
        student_id=student_id,
        course_id=course_id,
        topic_id=topic_id,
        title=content_json.get("title", f"{topic_name} — Revision Material"),
        material_type=material_type,
        language=language,
        depth=depth,
        grounded=1 if is_grounded else 0,
        content_json=content_json,
        personalization_summary=personalization,
        created_at=now,
        updated_at=now,
    )
    db.add(mat)
    db.commit()

    for s_info in verified_sources:
        src = RevisionMaterialSource(
            id=str(uuid.uuid4()).replace("-", ""),
            revision_material_id=mat_id,
            chunk_id=s_info.get("chunk_id"),
            file_name=s_info.get("file_name"),
            source_type=s_info.get("source_type"),
            page=s_info.get("page"),
            slide=s_info.get("slide"),
            timestamp_start=s_info.get("timestamp_start"),
            timestamp_end=s_info.get("timestamp_end"),
            created_at=now,
        )
        db.add(src)

    db.commit()

    return get_revision_material(db, mat_id, student_id=student_id)


def get_revision_material(
    db: Session,
    material_id: str,
    student_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve full revision material by ID, verifying student authorization."""
    mat = db.query(RevisionMaterial).filter(RevisionMaterial.id == material_id).first()
    if not mat:
        return None

    if student_id and mat.student_id != student_id:
        return {"error": "Unauthorized access to revision material."}

    sources = db.query(RevisionMaterialSource).filter(
        RevisionMaterialSource.revision_material_id == material_id
    ).all()

    sources_list = [
        {
            "chunk_id": s.chunk_id,
            "file_name": s.file_name,
            "source_type": s.source_type,
            "page": s.page,
            "slide": s.slide,
            "timestamp_start": s.timestamp_start,
            "timestamp_end": s.timestamp_end,
        }
        for s in sources
    ]

    return {
        "material_id": mat.id,
        "student_id": mat.student_id,
        "course_id": mat.course_id,
        "topic_id": mat.topic_id,
        "title": mat.title,
        "material_type": mat.material_type,
        "language": mat.language,
        "depth": mat.depth,
        "grounded": bool(mat.grounded),
        "content": mat.content_json,
        "personalization": mat.personalization_summary,
        "sources": sources_list,
        "created_at": mat.created_at.isoformat() if mat.created_at else None,
    }


def get_student_revision_materials(
    db: Session,
    student_id: str,
    course_id: str,
    material_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List revision materials saved for a student in a course."""
    query = db.query(RevisionMaterial).filter(
        RevisionMaterial.student_id == student_id,
        RevisionMaterial.course_id == course_id,
    )
    if material_type:
        query = query.filter(RevisionMaterial.material_type == material_type)

    mats = query.order_by(RevisionMaterial.created_at.desc()).all()

    return [
        {
            "material_id": m.id,
            "title": m.title,
            "material_type": m.material_type,
            "language": m.language,
            "depth": m.depth,
            "grounded": bool(m.grounded),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in mats
    ]


def delete_revision_material(db: Session, material_id: str, student_id: str) -> Dict[str, Any]:
    """Delete a saved revision material record."""
    mat = db.query(RevisionMaterial).filter(
        RevisionMaterial.id == material_id,
        RevisionMaterial.student_id == student_id,
    ).first()

    if not mat:
        return {"error": "Material not found or access denied."}

    db.delete(mat)
    db.commit()
    return {"success": True, "message": "Revision material deleted."}


def get_student_flashcard_decks(
    db: Session,
    student_id: str,
    course_id: str,
) -> List[Dict[str, Any]]:
    """List flashcard decks for a student in a course."""
    decks = (
        db.query(FlashcardDeck)
        .filter(FlashcardDeck.student_id == student_id, FlashcardDeck.course_id == course_id)
        .order_by(FlashcardDeck.created_at.desc())
        .all()
    )

    return [
        {
            "deck_id": d.id,
            "title": d.title,
            "language": d.language,
            "card_count": d.card_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in decks
    ]


def delete_flashcard_deck(db: Session, deck_id: str, student_id: str) -> Dict[str, Any]:
    """Delete a flashcard deck and all its cards and reviews."""
    deck = db.query(FlashcardDeck).filter(
        FlashcardDeck.id == deck_id,
        FlashcardDeck.student_id == student_id,
    ).first()

    if not deck:
        return {"error": "Deck not found or access denied."}

    db.delete(deck)
    db.commit()
    return {"success": True, "message": "Flashcard deck deleted."}
