"""
VIDYA-X AI — Knowledge Graph Service (Step 5)
Constructs relational graph structures (nodes & edges) from PostgreSQL tables
(concepts, relationships, prerequisites) to power visual concept maps and concept detail queries.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    Topic,
    Concept,
    Definition,
    Relationship,
    Prerequisite,
    ContentUnit,
)


def get_concept_graph(db: Session, course_id: str) -> Dict[str, Any]:
    """
    Construct nodes and edges representing the course knowledge graph.

    Args:
        db: SQLAlchemy session.
        course_id: The course identifier to extract graph for.

    Returns:
        Dictionary with 'nodes' and 'edges' arrays.
    """
    # 1. Fetch topics belonging to course
    topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    topic_ids = [t.id for t in topics]

    # 2. Fetch concepts belonging to these topics
    concepts = []
    if topic_ids:
        concepts = db.query(Concept).filter(Concept.topic_id.in_(topic_ids)).all()

    # Build node set
    nodes: List[Dict[str, Any]] = []
    concept_map = {}

    for c in concepts:
        concept_map[c.id] = c.name
        nodes.append({
            "id": c.id,
            "label": c.name,
            "type": "concept",
            "topic_id": c.topic_id,
            "difficulty": c.difficulty,
        })

    # 3. Fetch semantic relationships
    relationships = db.query(Relationship).filter(Relationship.course_id == course_id).all()

    edges: List[Dict[str, Any]] = []
    seen_edges = set()

    for r in relationships:
        edge_key = (r.from_concept_id, r.to_concept_id, r.relationship_type)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append({
                "from": r.from_concept_id,
                "to": r.to_concept_id,
                "type": r.relationship_type,
                "confidence": r.confidence,
            })

    # 4. Fetch prerequisites and add as directed edges
    prerequisites = db.query(Prerequisite).filter(Prerequisite.course_id == course_id).all()
    for p in prerequisites:
        edge_key = (p.prerequisite_concept_id, p.target_concept_id, "prerequisite_of")
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append({
                "from": p.prerequisite_concept_id,
                "to": p.target_concept_id,
                "type": "prerequisite_of",
                "reason": p.reason,
                "confidence": p.confidence,
            })

    return {
        "course_id": course_id,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


def get_concept_details(db: Session, concept_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve comprehensive details for a specific concept, including
    topic, definitions, prerequisites, related concepts, and source material.

    Args:
        db: SQLAlchemy session.
        concept_id: Concept identifier.

    Returns:
        Structured concept detail dictionary, or None if concept not found.
    """
    concept = db.get(Concept, concept_id)
    if not concept:
        return None

    # Fetch parent topic
    topic = db.get(Topic, concept.topic_id)
    topic_name = topic.name if topic else "General"

    # Fetch formal definitions
    definitions = [
        {"term": d.term, "definition": d.definition}
        for d in concept.definitions
    ]

    # Fetch prerequisites (concepts that must be learned before this one)
    prereq_records = db.query(Prerequisite).filter(Prerequisite.target_concept_id == concept_id).all()
    prerequisites = []
    for pr in prereq_records:
        pr_concept = db.get(Concept, pr.prerequisite_concept_id)
        prerequisites.append({
            "concept_id": pr.prerequisite_concept_id,
            "name": pr_concept.name if pr_concept else pr.prerequisite_concept_id,
            "reason": pr.reason,
        })

    # Fetch related concepts from relationships table
    rel_out = db.query(Relationship).filter(Relationship.from_concept_id == concept_id).all()
    rel_in = db.query(Relationship).filter(Relationship.to_concept_id == concept_id).all()

    related_concepts = []
    for r in rel_out:
        target = db.get(Concept, r.to_concept_id)
        related_concepts.append({
            "concept_id": r.to_concept_id,
            "name": target.name if target else r.to_concept_id,
            "relationship": r.relationship_type,
            "direction": "outgoing",
        })

    for r in rel_in:
        source = db.get(Concept, r.from_concept_id)
        related_concepts.append({
            "concept_id": r.from_concept_id,
            "name": source.name if source else r.from_concept_id,
            "relationship": r.relationship_type,
            "direction": "incoming",
        })

    return {
        "id": concept.id,
        "name": concept.name,
        "description": concept.description,
        "difficulty": concept.difficulty,
        "topic": topic_name,
        "definitions": definitions,
        "prerequisites": prerequisites,
        "related_concepts": related_concepts,
    }
