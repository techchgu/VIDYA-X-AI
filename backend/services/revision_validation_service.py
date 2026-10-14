"""
VIDYA-X AI — Revision Validation Service (Step 11)

Validates topics, concept ownership, and resolves citation references against actual
retrieved course content chunks. Rejects fabricated source IDs.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from database.models import Topic, Concept, KnowledgeChunk


def validate_topic_and_course(
    db: Session,
    course_id: str,
    topic_id: Optional[str] = None,
    concept_ids: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the requested topic_id and concept_ids belong to the specified course_id.
    Returns (is_valid, error_message).
    """
    if topic_id:
        t = db.query(Topic).filter(Topic.id == topic_id, Topic.course_id == course_id).first()
        if not t:
            return False, f"Topic '{topic_id}' does not belong to course '{course_id}'"

    if concept_ids:
        for cid in concept_ids:
            c = (
                db.query(Concept)
                .join(Topic, Concept.topic_id == Topic.id)
                .filter(Concept.id == cid, Topic.course_id == course_id)
                .first()
            )
            if not c:
                return False, f"Concept '{cid}' does not belong to course '{course_id}'"

    return True, None


def resolve_and_validate_citations(
    raw_citations: List[Any],
    source_map: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Resolve citation identifiers (e.g. 'SOURCE_1', chunk IDs) against the retrieved source_map.

    Returns:
        (resolved_citations, verified_sources_list)
    """
    resolved_citations = []
    verified_sources_dict = {}

    for cit in raw_citations:
        s_id = None
        if isinstance(cit, dict):
            s_id = cit.get("source_id") or cit.get("chunk_id") or cit.get("id")
        elif isinstance(cit, str):
            s_id = cit

        if not s_id:
            continue

        # Look up in source map
        chunk_data = source_map.get(s_id)
        if not chunk_data:
            # Try matching by chunk ID
            for key, cdata in source_map.items():
                if cdata.get("id") == s_id or key.lower() == str(s_id).lower():
                    chunk_data = cdata
                    s_id = key
                    break

        if chunk_data:
            meta = chunk_data.get("chunk_metadata") or {}
            resolved_ref = {
                "source_id": s_id,
                "chunk_id": chunk_data.get("id"),
                "file_name": chunk_data.get("file_name", "Course Document"),
                "source_type": chunk_data.get("source_type", "document"),
                "page": meta.get("page"),
                "slide": meta.get("slide"),
                "timestamp_start": meta.get("timestamp_start"),
                "timestamp_end": meta.get("timestamp_end"),
            }
            resolved_citations.append(resolved_ref)
            verified_sources_dict[chunk_data.get("id") or s_id] = resolved_ref

    return resolved_citations, list(verified_sources_dict.values())


def extract_source_map_from_chunks(
    chunks: List[Dict[str, Any]]
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Build SOURCE_1, SOURCE_2 lookup map and context text block from retrieved knowledge chunks.
    """
    source_map = {}
    context_lines = []

    for idx, chunk in enumerate(chunks, 1):
        s_key = f"SOURCE_{idx}"
        source_map[s_key] = chunk
        # Also map chunk ID directly
        if chunk.get("id"):
            source_map[chunk["id"]] = chunk

        meta = chunk.get("chunk_metadata") or {}
        ref_parts = [chunk.get("file_name", "Document")]
        if meta.get("page"):
            ref_parts.append(f"Page {meta['page']}")
        if meta.get("slide"):
            ref_parts.append(f"Slide {meta['slide']}")
        if meta.get("timestamp_start"):
            ref_parts.append(f"Time {meta['timestamp_start']}")

        ref_str = " — ".join(ref_parts)
        context_lines.append(f"[{s_key}] ({ref_str}):\n{chunk.get('content', '')}\n")

    context_text = "\n".join(context_lines)
    return source_map, context_text
