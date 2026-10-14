"""
VIDYA-X AI — Knowledge Structuring Service (Step 4 / 5 Support)
Extracts topics, concepts, definitions, relationships, and prerequisites from
extracted course units into structured JSON schema (saved in backend/structured/).
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List

STRUCTURED_DIR = Path(__file__).resolve().parent.parent / "structured"
EXTRACTED_DIR = Path(__file__).resolve().parent.parent / "extracted"


def _call_gemini_api(prompt: str, system_instruction: str = "", temperature: float = 0.2) -> str:
    """
    Helper function to call Gemini API if GEMINI_API_KEY is configured.
    Falls back gracefully or raises RuntimeError if key is missing/unavailable.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction if system_instruction else None,
        )
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature},
        )
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")


def ensure_structured_dir():
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)


def extract_structured_knowledge(file_id: str) -> Dict[str, Any]:
    """
    Load extracted content units for a file and synthesize structured knowledge:
    topics, concepts, definitions, relationships, and prerequisites.
    Saves and returns the structured JSON.
    """
    ensure_structured_dir()
    structured_path = STRUCTURED_DIR / f"{file_id}.json"

    # If already structured, return cached result
    if structured_path.exists():
        with open(structured_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Load raw extracted content from Step 3
    extracted_path = EXTRACTED_DIR / f"{file_id}.json"
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extracted content file not found for file_id '{file_id}'")

    with open(extracted_path, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)

    course_name = extracted_data.get("course_name", "General Course")
    units = extracted_data.get("units", [])

    # Heuristic / Rule-based Knowledge Structuring (compatible offline without API key)
    topics = []
    concepts = []
    definitions = []
    relationships = []
    prerequisites = []

    # 1. Main Topic derived from course or document
    topic_id = f"topic_{re.sub(r'[^a-zA-Z0-9]', '_', course_name).lower()}"
    topics.append({
        "id": topic_id,
        "name": course_name,
        "description": f"Core topics and concepts for {course_name}",
        "order_index": 1,
    })

    seen_concepts = set()

    for idx, u in enumerate(units):
        text = u.get("content", "")
        if not text:
            continue

        unit_id = u.get("unit_id", f"unit_{idx+1}")
        sentences = [s.strip() for s in re.split(r"[.\n]", text) if len(s.strip()) > 15]

        for s_idx, sentence in enumerate(sentences[:3]):
            # Detect definitions: "X is Y" or "X refers to Y" or "X: Y"
            def_match = re.search(r"^([A-Z][a-zA-Z0-9\s]{2,30}?)\s+(?:is|refers to|means|defines|states that)\s+(.+)", sentence, re.IGNORECASE)
            colon_match = re.search(r"^([A-Z][a-zA-Z0-9\s]{2,30}?):\s*(.+)", sentence)

            term = None
            def_text = None

            if def_match:
                term = def_match.group(1).strip()
                def_text = sentence
            elif colon_match:
                term = colon_match.group(1).strip()
                def_text = colon_match.group(2).strip()

            if term and len(term.split()) <= 4:
                concept_id = f"concept_{re.sub(r'[^a-zA-Z0-9]', '_', term).lower()}"

                if concept_id not in seen_concepts:
                    seen_concepts.add(concept_id)
                    concepts.append({
                        "id": concept_id,
                        "topic_id": topic_id,
                        "name": term.title(),
                        "description": def_text,
                        "difficulty": "medium",
                        "source_unit_id": unit_id,
                    })

                    definitions.append({
                        "id": f"def_{concept_id}",
                        "concept_id": concept_id,
                        "term": term.title(),
                        "definition": def_text,
                    })

    # If no explicit definitions detected, create foundational concepts from first units
    if not concepts:
        for idx, u in enumerate(units[:5]):
            content = u.get("content", "").strip()
            if not content:
                continue
            first_line = content.split("\n")[0][:50].strip() or f"Concept {idx+1}"
            concept_id = f"concept_{file_id}_{idx+1}"
            concepts.append({
                "id": concept_id,
                "topic_id": topic_id,
                "name": first_line.title(),
                "description": content[:200],
                "difficulty": "medium",
                "source_unit_id": u.get("unit_id"),
            })
            definitions.append({
                "id": f"def_{concept_id}",
                "concept_id": concept_id,
                "term": first_line.title(),
                "definition": content[:150],
            })

    # Synthesize sequential & prerequisite relationships between adjacent concepts
    for i in range(len(concepts) - 1):
        c1 = concepts[i]
        c2 = concepts[i+1]

        relationships.append({
            "id": f"rel_{c1['id']}_{c2['id']}",
            "from_concept_id": c1["id"],
            "relationship_type": "leads_to" if i % 2 == 0 else "related_to",
            "to_concept_id": c2["id"],
            "confidence": 0.9,
        })

        if i == 0 or i % 2 == 0:
            prerequisites.append({
                "id": f"prereq_{c1['id']}_{c2['id']}",
                "prerequisite_concept_id": c1["id"],
                "target_concept_id": c2["id"],
                "reason": f"Foundational understanding of {c1['name']} required for {c2['name']}",
                "confidence": 0.85,
            })

    structured_data = {
        "file_id": file_id,
        "course_name": course_name,
        "topics": topics,
        "concepts": concepts,
        "definitions": definitions,
        "relationships": relationships,
        "prerequisites": prerequisites,
    }

    # Save to disk
    with open(structured_path, "w", encoding="utf-8") as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=2)

    return structured_data
