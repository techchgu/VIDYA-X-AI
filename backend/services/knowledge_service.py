"""
VIDYA-X AI — Knowledge Ingestion Service (Step 5)
Ingests extracted content units and structured knowledge (topics, concepts, definitions,
relationships, prerequisites) into PostgreSQL. Generates vector embeddings for content
chunks and persists them into the pgvector knowledge_chunks table with deduplication.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from database.models import (
    Course,
    Material,
    ContentUnit,
    Topic,
    Concept,
    Definition,
    Relationship,
    Prerequisite,
    KnowledgeChunk,
)
from services.embedding_service import generate_embeddings
from services.llm_service import extract_structured_knowledge

EXTRACTED_DIR = Path(__file__).resolve().parent.parent / "extracted"


def slugify(text: str) -> str:
    """Convert text into a stable, clean identifier slug."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", slug) or "default"


def ingest_file_knowledge(file_id: str, db: Session) -> Dict[str, Any]:
    """
    Ingest extracted and structured course knowledge into PostgreSQL + pgvector.
    Idempotent upsert strategy prevents duplicate records across multiple runs.

    Args:
        file_id: The identifier of the uploaded and extracted material.
        db: SQLAlchemy database session.

    Returns:
        Ingestion statistics dictionary.
    """
    # 1. Load Step 3 extracted units
    extracted_path = EXTRACTED_DIR / f"{file_id}.json"
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extraction file for '{file_id}' not found in backend/extracted/")

    with open(extracted_path, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)

    file_name = extracted_data.get("file_name", "unknown_file")
    course_name = extracted_data.get("course_name", "General").strip() or "General"
    source_type = extracted_data.get("source_type", "document")
    units = extracted_data.get("units", [])

    # 2. Load or generate Step 4 structured knowledge
    structured_data = extract_structured_knowledge(file_id)

    # 3. Upsert Course
    course_id = f"course_{slugify(course_name)}"
    course = db.get(Course, course_id)
    if not course:
        course = Course(id=course_id, name=course_name)
        db.add(course)
        db.flush()

    # 4. Upsert Material
    material = db.get(Material, file_id)
    if not material:
        material = Material(
            id=file_id,
            course_id=course_id,
            file_name=file_name,
            source_type=source_type,
            file_path=str(extracted_path),
            status="processed",
        )
        db.add(material)
    else:
        material.status = "processed"
    db.flush()

    # 5. Upsert Content Units
    for u in units:
        unit_key = f"{file_id}_{u.get('unit_id')}"
        unit_record = db.get(ContentUnit, unit_key)
        if not unit_record:
            unit_record = ContentUnit(
                id=unit_key,
                material_id=file_id,
                unit_id=u.get("unit_id"),
                content=u.get("content", ""),
                page=u.get("page"),
                slide=u.get("slide"),
                timestamp_start=u.get("timestamp_start"),
                timestamp_end=u.get("timestamp_end"),
                unit_metadata=u.get("metadata", {}),
            )
            db.add(unit_record)
        else:
            unit_record.content = u.get("content", "")
            unit_record.page = u.get("page")
            unit_record.slide = u.get("slide")
            unit_record.timestamp_start = u.get("timestamp_start")
            unit_record.timestamp_end = u.get("timestamp_end")
    db.flush()

    # 6. Upsert Topics
    topics_list = structured_data.get("topics", [])
    for t in topics_list:
        topic_id = t.get("id")
        topic_record = db.get(Topic, topic_id)
        if not topic_record:
            topic_record = Topic(
                id=topic_id,
                course_id=course_id,
                name=t.get("name"),
                description=t.get("description"),
                order_index=t.get("order_index", 0),
            )
            db.add(topic_record)
        else:
            topic_record.name = t.get("name")
            topic_record.description = t.get("description")
    db.flush()

    # 7. Upsert Concepts
    concepts_list = structured_data.get("concepts", [])
    for c in concepts_list:
        concept_id = c.get("id")
        concept_record = db.get(Concept, concept_id)
        if not concept_record:
            concept_record = Concept(
                id=concept_id,
                topic_id=c.get("topic_id"),
                name=c.get("name"),
                description=c.get("description"),
                difficulty=c.get("difficulty", "medium"),
            )
            db.add(concept_record)
        else:
            concept_record.name = c.get("name")
            concept_record.description = c.get("description")
            concept_record.difficulty = c.get("difficulty", "medium")
    db.flush()

    # 8. Upsert Definitions
    definitions_list = structured_data.get("definitions", [])
    for d in definitions_list:
        def_id = d.get("id")
        def_record = db.get(Definition, def_id)
        if not def_record:
            def_record = Definition(
                id=def_id,
                concept_id=d.get("concept_id"),
                term=d.get("term"),
                definition=d.get("definition"),
            )
            db.add(def_record)
        else:
            def_record.term = d.get("term")
            def_record.definition = d.get("definition")
    db.flush()

    # 9. Upsert Relationships
    relationships_list = structured_data.get("relationships", [])
    for r in relationships_list:
        rel_id = r.get("id")
        rel_record = db.get(Relationship, rel_id)
        if not rel_record:
            rel_record = Relationship(
                id=rel_id,
                course_id=course_id,
                from_concept_id=r.get("from_concept_id"),
                relationship_type=r.get("relationship_type"),
                to_concept_id=r.get("to_concept_id"),
                confidence=r.get("confidence", 1.0),
            )
            db.add(rel_record)
    db.flush()

    # 10. Upsert Prerequisites
    prereqs_list = structured_data.get("prerequisites", [])
    for p in prereqs_list:
        prereq_id = p.get("id")
        prereq_record = db.get(Prerequisite, prereq_id)
        if not prereq_record:
            prereq_record = Prerequisite(
                id=prereq_id,
                course_id=course_id,
                prerequisite_concept_id=p.get("prerequisite_concept_id"),
                target_concept_id=p.get("target_concept_id"),
                reason=p.get("reason"),
                confidence=p.get("confidence", 1.0),
            )
            db.add(prereq_record)
    db.flush()

    # 11. Build Knowledge Chunks to Embed
    # Chunks are created from:
    #   a) Educational content units
    #   b) Formal definitions
    #   c) Concept descriptions
    raw_chunks: List[Dict[str, Any]] = []

    # a) Content units
    for u in units:
        content = u.get("content", "").strip()
        if not content:
            continue
        chunk_id = f"chunk_unit_{file_id}_{u.get('unit_id')}"
        raw_chunks.append({
            "id": chunk_id,
            "content_unit_id": u.get("unit_id"),
            "content": content,
            "chunk_type": "content_unit",
            "metadata": {
                "file_name": file_name,
                "source_type": source_type,
                "page": u.get("page"),
                "slide": u.get("slide"),
                "timestamp_start": u.get("timestamp_start"),
                "timestamp_end": u.get("timestamp_end"),
                "unit_id": u.get("unit_id"),
            },
        })

    # b) Definitions
    for d in definitions_list:
        term = d.get("term", "").strip()
        defn = d.get("definition", "").strip()
        if not term or not defn:
            continue
        chunk_id = f"chunk_def_{d.get('id')}"
        raw_chunks.append({
            "id": chunk_id,
            "content_unit_id": None,
            "content": f"{term}: {defn}",
            "chunk_type": "definition",
            "metadata": {
                "file_name": file_name,
                "source_type": source_type,
                "term": term,
                "concept_id": d.get("concept_id"),
            },
        })

    # c) Concepts
    for c in concepts_list:
        c_name = c.get("name", "").strip()
        c_desc = c.get("description", "").strip()
        if not c_name:
            continue
        chunk_id = f"chunk_concept_{c.get('id')}"
        raw_chunks.append({
            "id": chunk_id,
            "content_unit_id": c.get("source_unit_id"),
            "content": f"{c_name}: {c_desc}" if c_desc else c_name,
            "chunk_type": "concept",
            "metadata": {
                "file_name": file_name,
                "source_type": source_type,
                "concept_name": c_name,
                "concept_id": c.get("id"),
            },
        })

    # 12. Generate Embeddings & Upsert Chunks
    if raw_chunks:
        texts_to_embed = [c["content"] for c in raw_chunks]
        embeddings = generate_embeddings(texts_to_embed)

        for chunk_data, emb in zip(raw_chunks, embeddings):
            chunk_id = chunk_data["id"]
            chunk_record = db.get(KnowledgeChunk, chunk_id)
            if not chunk_record:
                chunk_record = KnowledgeChunk(
                    id=chunk_id,
                    course_id=course_id,
                    material_id=file_id,
                    content_unit_id=chunk_data["content_unit_id"],
                    content=chunk_data["content"],
                    chunk_type=chunk_data["chunk_type"],
                    embedding=emb,
                    chunk_metadata=chunk_data["metadata"],
                )
                db.add(chunk_record)
            else:
                chunk_record.content = chunk_data["content"]
                chunk_record.embedding = emb
                chunk_record.chunk_metadata = chunk_data["metadata"]

    db.commit()

    return {
        "success": True,
        "file_id": file_id,
        "course_id": course_id,
        "course_name": course_name,
        "topics": len(topics_list),
        "concepts": len(concepts_list),
        "definitions": len(definitions_list),
        "relationships": len(relationships_list),
        "prerequisites": len(prereqs_list),
        "chunks_created": len(raw_chunks),
        "embeddings_created": len(raw_chunks),
    }
