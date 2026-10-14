"""
VIDYA-X AI — Grounded AI Tutor Service (Step 6 / Step 15 Integration)
Provides grounded, source-cited conversational answers strictly derived from course materials.
Safely abstains when retrieved course evidence is absent or insufficient.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import Course, KnowledgeChunk
from services.search_service import semantic_search
from services.llm_service import _call_gemini_api

logger = logging.getLogger(__name__)

SIMILARITY_ABSTENTION_THRESHOLD = 0.15  # Compatible with local normalized n-gram sparse projections


def answer_student_question(
    db: Session,
    course_id: str,
    question: str,
    top_k: int = 4,
    preferred_language: str = "English",
) -> Dict[str, Any]:
    """
    Generate a grounded response to a student question using retrieved course chunks.

    Returns:
        dict containing:
            answer: Grounded explanation or safe abstention statement
            supported: bool (True if answer is grounded in course materials)
            citations: List of source reference dicts (file_name, page, slide, timestamp, chunk_id)
            chunks_used: count of chunks retrieved
    """
    clean_question = (question or "").strip()
    if not clean_question:
        return {
            "answer": "Please ask a question about your course materials.",
            "supported": False,
            "citations": [],
            "chunks_used": 0,
        }

    # 1. Retrieve course-isolated knowledge chunks (both text & visual descriptions)
    chunks = semantic_search(db=db, course_id=course_id, query=clean_question, top_k=top_k)

    # 2. Check evidence sufficiency: both vector similarity and lexical term overlap
    stopwords = {"what", "is", "the", "in", "of", "and", "a", "an", "to", "how", "why", "who", "for", "on", "with", "as", "by", "at"}
    q_words = [w.lower().strip("?,.!") for w in clean_question.split() if len(w) > 2 and w.lower() not in stopwords]

    # Check if key query terms appear in retrieved chunk texts
    has_lexical_match = False
    for c in chunks:
        c_text = (c.get("content") or "").lower()
        if any(w in c_text for w in q_words):
            has_lexical_match = True
            break

    top_score = max((c.get("score", 0.0) for c in chunks), default=0.0)
    is_supported = (top_score >= SIMILARITY_ABSTENTION_THRESHOLD) and has_lexical_match

    if not chunks or not is_supported:
        return {
            "answer": (
                "I couldn't find sufficient information in your uploaded course materials to answer this question. "
                "To maintain academic accuracy, I only answer based on verified course content. "
                "Please upload or review materials covering this topic."
            ),
            "supported": False,
            "citations": [],
            "chunks_used": len(chunks),
        }

    # 3. Assemble citation metadata
    citations = []
    context_blocks = []
    seen_refs = set()

    for idx, c in enumerate(chunks, 1):
        src = c.get("source", {})
        file_name = src.get("file_name") or "Course Material"
        page = src.get("page")
        slide = src.get("slide")
        ts = src.get("timestamp_start")
        is_visual = c.get("is_visual", False)
        chunk_type = c.get("chunk_type", "text")

        loc_parts = []
        if page:
            loc_parts.append(f"Page {page}")
        if slide:
            loc_parts.append(f"Slide {slide}")
        if ts:
            loc_parts.append(f"Timestamp {ts}")
        loc_str = ", ".join(loc_parts) or "General"

        ref_key = f"{file_name}:{loc_str}"
        if ref_key not in seen_refs:
            seen_refs.add(ref_key)
            citations.append({
                "citation_id": f"[{idx}]",
                "file_name": file_name,
                "location": loc_str,
                "page": page,
                "slide": slide,
                "timestamp": ts,
                "is_visual": is_visual,
                "chunk_id": c.get("chunk_id"),
                "excerpt": c.get("content", "")[:180] + "...",
            })

        context_blocks.append(f"SOURCE [{idx}] ({file_name}, {loc_str}):\n{c.get('content', '')}")

    context_text = "\n\n".join(context_blocks)

    # 4. Generate answer via LLM (or deterministic grounded fallback)
    lang_prompt = (
        f"Respond in {preferred_language}."
        if preferred_language in ("Hindi", "Hinglish")
        else "Respond in clear English."
    )

    sys_instruction = (
        "You are VIDYA-X AI, a course-aware AI tutor. "
        "Your answers must be grounded STRICTLY in the provided course excerpts. "
        "Include source citation brackets like [1], [2] when stating factual claims from a source. "
        "If an answer cannot be determined from the excerpts, explicitly say so."
    )

    prompt = f"""{sys_instruction}
{lang_prompt}

STUDENT QUESTION:
{clean_question}

COURSE EXCERPTS:
{context_text}

Provide a clear, pedagogical explanation with inline citations matching the sources."""

    try:
        response_text = _call_gemini_api(prompt, system_instruction=sys_instruction, temperature=0.2)
        answer = response_text.strip()
    except Exception as exc:
        logger.warning(f"Tutor LLM generation fallback: {exc}")
        # Deterministic grounded synthesis fallback
        top_chunk = chunks[0]
        top_src = citations[0] if citations else {}
        loc = top_src.get("location", "Course Notes")
        fname = top_src.get("file_name", "your course material")
        answer = (
            f"Based on {fname} ({loc}) [1]:\n\n"
            f"{top_chunk.get('content', '').strip()}\n\n"
            f"This addresses your question regarding '{clean_question}' directly from your syllabus."
        )

    return {
        "answer": answer,
        "supported": True,
        "citations": citations,
        "chunks_used": len(chunks),
    }
