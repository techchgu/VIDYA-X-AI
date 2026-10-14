"""
VIDYA-X AI — Visual Retrieval Service (Step 14)
Performs semantic retrieval across indexed visual knowledge descriptions and
exposes endpoints for listing and inspecting course visual assets.
Strictly enforces course boundary isolation.
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import KnowledgeChunk, VisualAsset
from database.connection import is_sqlite
from services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)


def search_visual_descriptions(
    db: Session,
    course_id: str,
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Search course visual description chunks using vector semantic similarity with strict course isolation.
    Returns results matching search_service schema for seamless RAG fusion.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        return []

    query_vector = generate_embedding(clean_query)
    results: List[Dict[str, Any]] = []

    if not is_sqlite:
        cosine_dist = KnowledgeChunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(KnowledgeChunk, cosine_dist.label("distance"))
            .filter(
                KnowledgeChunk.course_id == course_id,
                KnowledgeChunk.chunk_type == "visual_description",
            )
            .order_by(cosine_dist.asc())
            .limit(top_k)
        )
        rows = db.execute(stmt).all()
        for chunk, dist in rows:
            score = max(0.0, round(1.0 - float(dist), 4))
            results.append(_format_visual_chunk(chunk, score))
    else:
        # SQLite fallback for offline unit tests
        import math

        def cosine_sim(v1, v2):
            if not v1 or not v2:
                return 0.0
            dot = sum(a * b for a, b in zip(v1, v2))
            n1 = math.sqrt(sum(a * a for a in v1))
            n2 = math.sqrt(sum(b * b for b in v2))
            return dot / (n1 * n2) if (n1 > 0 and n2 > 0) else 0.0

        chunks = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.course_id == course_id,
                KnowledgeChunk.chunk_type == "visual_description",
            )
            .all()
        )
        scored = []
        for ch in chunks:
            vec = ch.embedding
            if hasattr(vec, "tolist"):
                vec = vec.tolist()
            sim = cosine_sim(query_vector, vec)
            scored.append((ch, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        for chunk, sim in scored[:top_k]:
            results.append(_format_visual_chunk(chunk, round(float(sim), 4)))

    return results


def _format_visual_chunk(chunk: KnowledgeChunk, score: float) -> Dict[str, Any]:
    meta = chunk.chunk_metadata or {}
    return {
        "chunk_id": chunk.id,
        "content": chunk.content,
        "chunk_type": "visual_description",
        "score": score,
        "is_visual": True,
        "source": {
            "file_name": meta.get("file_name"),
            "source_type": meta.get("source_type"),
            "page": meta.get("page"),
            "slide": meta.get("slide"),
            "timestamp_start": meta.get("timestamp_start"),
            "timestamp_end": meta.get("timestamp_end"),
            "visual_asset_id": meta.get("visual_asset_id"),
            "asset_type": meta.get("asset_type"),
            "unit_id": chunk.content_unit_id or meta.get("unit_id"),
        },
    }


def list_course_visual_assets(
    db: Session,
    course_id: str,
    source_type: Optional[str] = None,
    asset_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Retrieve paginated list of visual assets belonging to a specific course."""
    query = db.query(VisualAsset).filter(VisualAsset.course_id == course_id)
    if source_type:
        query = query.filter(VisualAsset.source_type == source_type)
    if asset_type:
        query = query.filter(VisualAsset.asset_type == asset_type)

    total = query.count()
    offset = max(0, (page - 1) * page_size)
    assets = (
        query.order_by(VisualAsset.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "course_id": course_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "assets": [_serialize_visual_asset(a) for a in assets],
    }


def get_visual_asset_detail(
    db: Session,
    asset_id: str,
    course_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve full details of a visual asset, optionally verifying course ownership."""
    va = db.get(VisualAsset, asset_id)
    if not va:
        return None
    if course_id and va.course_id != course_id:
        return None
    return _serialize_visual_asset(va, include_structured=True)


def _serialize_visual_asset(va: VisualAsset, include_structured: bool = False) -> Dict[str, Any]:
    """Serialize VisualAsset without exposing sensitive server filesystem paths."""
    data = {
        "id": va.id,
        "course_id": va.course_id,
        "material_id": va.material_id,
        "source_file_name": va.source_file_name,
        "source_type": va.source_type,
        "asset_type": va.asset_type,
        "page_number": va.page_number,
        "slide_number": va.slide_number,
        "timestamp_start": va.timestamp_start,
        "timestamp_end": va.timestamp_end,
        "visual_description": va.visual_description,
        "processing_status": va.processing_status,
        "processing_error": va.processing_error,
        "has_image": bool(va.image_path),
        "knowledge_chunk_id": va.knowledge_chunk_id,
        "created_at": va.created_at.isoformat() if va.created_at else None,
    }
    if include_structured:
        data["structured_description"] = va.structured_description
    return data
