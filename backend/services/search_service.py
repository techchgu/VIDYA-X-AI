"""
VIDYA-X AI — Semantic Vector Search Service (Step 5)
Performs vector similarity search over pgvector knowledge chunks with strict course isolation.
Uses pgvector cosine distance operator for high-performance ranking.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import KnowledgeChunk
from database.connection import is_sqlite
from services.embedding_service import generate_embedding


def semantic_search(
    db: Session,
    course_id: str,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search course knowledge chunks using vector semantic similarity with strict course isolation.

    Args:
        db: SQLAlchemy session.
        course_id: The specific course identifier to isolate results.
        query: Student question or search term.
        top_k: Number of most relevant knowledge chunks to return.

    Returns:
        List of structured search result items with similarity scores and exact source citations.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        return []

    # 1. Generate query embedding vector
    query_vector = generate_embedding(clean_query)

    # 2. Vector search query
    results: List[Dict[str, Any]] = []

    if not is_sqlite:
        # Native pgvector cosine distance operator: <=>
        # Cosine distance ranges from 0.0 (identical) to 2.0 (opposite)
        # Similarity score = 1.0 - distance
        cosine_dist = KnowledgeChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(KnowledgeChunk, cosine_dist.label("distance"))
            .filter(KnowledgeChunk.course_id == course_id)
            .order_by(cosine_dist.asc())
            .limit(top_k)
        )

        rows = db.execute(stmt).all()

        for chunk, dist in rows:
            score = max(0.0, round(1.0 - float(dist), 4))
            meta = chunk.chunk_metadata or {}

            results.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "chunk_type": chunk.chunk_type,
                "score": score,
                "is_visual": meta.get("is_visual", False) or chunk.chunk_type == "visual_description",
                "source": {
                    "file_name": meta.get("file_name"),
                    "source_type": meta.get("source_type"),
                    "page": meta.get("page"),
                    "slide": meta.get("slide"),
                    "timestamp_start": meta.get("timestamp_start"),
                    "timestamp_end": meta.get("timestamp_end"),
                    "unit_id": chunk.content_unit_id or meta.get("unit_id"),
                    "visual_asset_id": meta.get("visual_asset_id"),
                    "asset_type": meta.get("asset_type"),
                },
            })

    else:
        # Fallback for SQLite / unit testing without live PostgreSQL instance
        import math

        def cosine_sim(v1, v2):
            if not v1 or not v2:
                return 0.0
            dot = sum(a * b for a, b in zip(v1, v2))
            n1 = math.sqrt(sum(a * a for a in v1))
            n2 = math.sqrt(sum(b * b for b in v2))
            return dot / (n1 * n2) if (n1 > 0 and n2 > 0) else 0.0

        all_chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.course_id == course_id).all()
        scored = []
        for ch in all_chunks:
            # Check vector or list
            vec = ch.embedding
            if hasattr(vec, "tolist"):
                vec = vec.tolist()
            sim = cosine_sim(query_vector, vec)
            scored.append((ch, sim))

        scored.sort(key=lambda x: x[1], reverse=True)

        for chunk, sim in scored[:top_k]:
            meta = chunk.chunk_metadata or {}
            results.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "chunk_type": chunk.chunk_type,
                "score": round(float(sim), 4),
                "is_visual": meta.get("is_visual", False) or chunk.chunk_type == "visual_description",
                "source": {
                    "file_name": meta.get("file_name"),
                    "source_type": meta.get("source_type"),
                    "page": meta.get("page"),
                    "slide": meta.get("slide"),
                    "timestamp_start": meta.get("timestamp_start"),
                    "timestamp_end": meta.get("timestamp_end"),
                    "unit_id": chunk.content_unit_id or meta.get("unit_id"),
                    "visual_asset_id": meta.get("visual_asset_id"),
                    "asset_type": meta.get("asset_type"),
                },
            })

    return results
