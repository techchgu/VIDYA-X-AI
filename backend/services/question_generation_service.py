"""
VIDYA-X AI — Question Generation Service (Step 7)
Heuristic question generation grounded EXCLUSIVELY in course knowledge chunks.
Uses semantic_search() to retrieve relevant content then applies template rules
to create MCQ, short-answer, and numerical questions — NO hallucination allowed.
Works without any external LLM API (no OpenAI / Gemini required).
"""

import re
import random
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from services.search_service import semantic_search
from services.question_service import compute_fingerprint, question_exists, store_question


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_questions(
    db: Session,
    course_id: str,
    topic_query: str,
    question_types: Optional[List[str]] = None,
    count: int = 5,
    difficulty: str = "medium",
) -> List[Dict[str, Any]]:
    """
    Generate grounded questions from course knowledge chunks.

    Steps:
      1. Retrieve top-K knowledge chunks via semantic_search().
      2. Classify each chunk as definition / concept / numerical.
      3. Apply template generators to produce candidate questions.
      4. Deduplicate via fingerprint.
      5. Store new questions and return list.

    Args:
        db: SQLAlchemy session.
        course_id: Restrict retrieval to this course.
        topic_query: Free-text query to drive semantic retrieval.
        question_types: Subset of ['mcq', 'short_answer', 'numerical']. None = all.
        count: Maximum number of questions to return.
        difficulty: 'easy' | 'medium' | 'hard'

    Returns:
        List of stored question dicts (without correct_answer exposed).
    """
    if question_types is None:
        question_types = ["mcq", "short_answer", "numerical"]

    # 1. Retrieve grounding chunks
    raw_chunks = semantic_search(db, course_id, topic_query, top_k=30)
    if not raw_chunks:
        return []

    # 2. Separate definition / concept chunks from numerical chunks
    def_chunks = [c for c in raw_chunks if c["chunk_type"] in ("definition", "concept")]
    num_chunks = [c for c in raw_chunks if _has_numbers(c["content"])]
    all_concept_names = _extract_concept_names(def_chunks)

    # 3. Build candidate questions
    candidates: List[Dict[str, Any]] = []

    if "mcq" in question_types:
        candidates += _generate_mcq(def_chunks, all_concept_names, course_id, difficulty)

    if "short_answer" in question_types:
        candidates += _generate_short_answer(def_chunks, raw_chunks, course_id, difficulty)

    if "numerical" in question_types:
        candidates += _generate_numerical(num_chunks, course_id, difficulty)

    # 4. Shuffle so we get variety across types
    random.shuffle(candidates)

    # 5. Deduplicate, store, and collect results
    results: List[Dict[str, Any]] = []
    for candidate in candidates:
        if len(results) >= count:
            break
        fp = compute_fingerprint(candidate["prompt"])
        candidate["fingerprint"] = fp
        if question_exists(db, fp):
            continue  # skip exact duplicates
        q_id = store_question(db, candidate)
        results.append({
            "id": q_id,
            "question_type": candidate["question_type"],
            "prompt": candidate["prompt"],
            "difficulty": candidate["difficulty"],
            "source_refs": candidate.get("source_refs", []),
            **({"options": [{"key": o["key"], "text": o["text"]} for o in candidate.get("options", [])]}
               if candidate["question_type"] == "mcq" else {}),
        })

    return results


# ---------------------------------------------------------------------------
# MCQ generator
# ---------------------------------------------------------------------------

def _generate_mcq(
    def_chunks: List[Dict],
    all_concept_names: List[str],
    course_id: str,
    difficulty: str,
) -> List[Dict[str, Any]]:
    questions = []
    seen_terms: set = set()

    for chunk in def_chunks:
        content = chunk["content"].strip()
        # Try to parse "Term is/are Definition" patterns
        term, definition = _parse_definition(content)
        if not term or not definition or term.lower() in seen_terms:
            continue
        seen_terms.add(term.lower())

        prompt = f'What is the correct definition of "{term}"?'
        correct_option = definition[:300]  # cap length

        # Build distractors from other concept names in this retrieval context
        distractors = _build_distractors(term, all_concept_names, content)
        if len(distractors) < 3:
            continue  # need at least 3 distractors for a 4-option MCQ

        options_text = [correct_option] + distractors[:3]
        random.shuffle(options_text)

        options = []
        correct_key = ""
        for key, text in zip(["A", "B", "C", "D"], options_text):
            is_correct = text == correct_option
            if is_correct:
                correct_key = key
            options.append({"key": key, "text": text, "is_correct": is_correct})

        questions.append({
            "course_id": course_id,
            "question_type": "mcq",
            "prompt": prompt,
            "difficulty": difficulty,
            "correct_answer": correct_key,
            "explanation": f'The correct definition comes from: "{content[:200]}"',
            "options": options,
            "source_refs": [_build_ref(chunk)],
        })

    return questions


# ---------------------------------------------------------------------------
# Short-answer generator
# ---------------------------------------------------------------------------

def _generate_short_answer(
    def_chunks: List[Dict],
    all_chunks: List[Dict],
    course_id: str,
    difficulty: str,
) -> List[Dict[str, Any]]:
    questions = []
    seen_prompts: set = set()

    # Template 1: "What is X?" from definition chunks
    for chunk in def_chunks:
        content = chunk["content"].strip()
        term, definition = _parse_definition(content)
        if not term or not definition:
            continue
        prompt = f"What is {term}?"
        if prompt in seen_prompts:
            continue
        seen_prompts.add(prompt)
        questions.append({
            "course_id": course_id,
            "question_type": "short_answer",
            "prompt": prompt,
            "difficulty": difficulty,
            "correct_answer": definition[:500],
            "explanation": f'From course material: "{content[:300]}"',
            "source_refs": [_build_ref(chunk)],
        })

    # Template 2: "Explain …" from longer concept chunks
    for chunk in all_chunks:
        if chunk["chunk_type"] not in ("concept", "content_unit"):
            continue
        content = chunk["content"].strip()
        if len(content) < 80:
            continue
        # Extract the first noun phrase / subject of the chunk for the prompt
        subject = _extract_subject(content)
        if not subject or len(subject) < 4:
            continue
        prompt = f"Explain the concept of {subject}."
        if prompt in seen_prompts:
            continue
        seen_prompts.add(prompt)
        questions.append({
            "course_id": course_id,
            "question_type": "short_answer",
            "prompt": prompt,
            "difficulty": difficulty,
            "correct_answer": content[:500],
            "explanation": f'Reference: "{content[:300]}"',
            "source_refs": [_build_ref(chunk)],
        })

    return questions


# ---------------------------------------------------------------------------
# Numerical generator
# ---------------------------------------------------------------------------

def _generate_numerical(
    num_chunks: List[Dict],
    course_id: str,
    difficulty: str,
) -> List[Dict[str, Any]]:
    questions = []
    seen_prompts: set = set()

    for chunk in num_chunks:
        content = chunk["content"].strip()
        # Look for formula-like sentences: "X = Y" or "X equals Y"
        formula_match = re.search(
            r"([A-Za-z][A-Za-z\s]{0,30}?)\s*=\s*([\d\.\+\-\*\/\(\)\s]{1,60})",
            content,
        )
        if formula_match:
            lhs = formula_match.group(1).strip()
            rhs = formula_match.group(2).strip()
            prompt = f"According to the course material, what is the value or formula for '{lhs}'?"
            if prompt in seen_prompts:
                continue
            seen_prompts.add(prompt)
            questions.append({
                "course_id": course_id,
                "question_type": "numerical",
                "prompt": prompt,
                "difficulty": difficulty,
                "correct_answer": rhs,
                "explanation": f'From course material: "{content[:300]}"',
                "solution": f"{lhs} = {rhs}\n\nSource: {content[:300]}",
                "source_refs": [_build_ref(chunk)],
            })
        else:
            # Generic: "What numerical value is associated with …?"
            numbers = re.findall(r"\b\d+(?:\.\d+)?\b", content)
            subject = _extract_subject(content)
            if numbers and subject and len(subject) >= 4:
                prompt = f"What numerical value is associated with '{subject}' as stated in the course material?"
                if prompt in seen_prompts:
                    continue
                seen_prompts.add(prompt)
                questions.append({
                    "course_id": course_id,
                    "question_type": "numerical",
                    "prompt": prompt,
                    "difficulty": difficulty,
                    "correct_answer": numbers[0],
                    "explanation": f'From course material: "{content[:300]}"',
                    "source_refs": [_build_ref(chunk)],
                })

    return questions


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_definition(text: str):
    """
    Try to extract (term, definition) from common definition patterns:
      - "X is Y"
      - "X are Y"
      - "X: Y"
      - "X refers to Y"
      - "X means Y"
    Returns (None, None) if no pattern matched.
    """
    patterns = [
        r"^([A-Za-z][A-Za-z0-9\s\-]{1,60}?)\s+(?:is|are|refers to|means)\s+(.+)$",
        r"^([A-Za-z][A-Za-z0-9\s\-]{1,60}?):\s+(.+)$",
    ]
    for pat in patterns:
        m = re.match(pat, text.strip(), re.IGNORECASE | re.DOTALL)
        if m:
            term = m.group(1).strip()
            definition = m.group(2).strip()
            # Sanity: term must be ≤ 8 words
            if len(term.split()) <= 8 and len(definition) >= 10:
                return term, definition
    return None, None


def _extract_concept_names(chunks: List[Dict]) -> List[str]:
    """Extract all term names from definition chunks."""
    names = []
    for c in chunks:
        term, _ = _parse_definition(c["content"])
        if term:
            names.append(term)
    return names


def _build_distractors(correct_term: str, all_names: List[str], source_text: str) -> List[str]:
    """
    Build distractor option texts for MCQ. Uses other concept names as wrong answers.
    Pads with generic fallback strings if not enough real distractors available.
    """
    distractors = []
    for name in all_names:
        if name.lower() == correct_term.lower():
            continue
        distractors.append(f"A concept related to {name}")
    # Generic fallbacks to ensure we always have at least 3
    fallbacks = [
        "None of the above options are correct",
        "This term has no standard definition in the course",
        "A general process without a specific definition",
        "An undefined concept in this course material",
    ]
    for fb in fallbacks:
        if len(distractors) >= 3:
            break
        distractors.append(fb)
    return distractors


def _extract_subject(text: str) -> str:
    """Extract first 1-5 word noun phrase from the start of a text chunk."""
    # Take first sentence
    sentence = re.split(r"[.!?]", text)[0].strip()
    words = sentence.split()
    # Skip articles and return first ≤5 content words
    skip = {"the", "a", "an", "in", "of", "on", "at", "by", "for", "is", "are", "was", "were"}
    content_words = [w for w in words if w.lower() not in skip]
    return " ".join(content_words[:5])


def _has_numbers(text: str) -> bool:
    """Return True if text contains at least one standalone number."""
    return bool(re.search(r"\b\d+(?:\.\d+)?\b", text))


def _build_ref(chunk: Dict) -> Dict[str, Any]:
    """Build a source reference dict from a search result chunk."""
    src = chunk.get("source", {})
    return {
        "chunk_id": chunk.get("chunk_id"),
        "file_name": src.get("file_name"),
        "source_type": src.get("source_type"),
        "page": src.get("page"),
        "slide": src.get("slide"),
        "timestamp_start": src.get("timestamp_start"),
        "timestamp_end": src.get("timestamp_end"),
    }
