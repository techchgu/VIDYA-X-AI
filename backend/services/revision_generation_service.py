"""
VIDYA-X AI — Revision Generation Service (Step 11)

Generates structured, grounded revision materials for 8+ material types:
  - topic_summary
  - revision_notes
  - exam_revision_sheet
  - formula_sheet
  - concept_comparison
  - definitions_terminology
  - quick_checklist
  - weak_topic_study_guide

Supports depth (concise, standard, detailed) and language (English, Hindi, Hinglish).
Uses _call_gemini_api with structured JSON prompts and provides an offline fallback generator.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from services.llm_service import _call_gemini_api

logger = logging.getLogger(__name__)

MATERIAL_TYPE_TITLES = {
    "topic_summary": "Topic Summary",
    "revision_notes": "Detailed Revision Notes",
    "exam_revision_sheet": "Exam Revision Sheet",
    "formula_sheet": "Formula & Variable Sheet",
    "concept_comparison": "Concept Comparison Table",
    "definitions_terminology": "Key Definitions & Terminology",
    "quick_checklist": "Quick-Review Checklist",
    "weak_topic_study_guide": "Targeted Weak-Topic Study Guide",
}


def generate_revision_content(
    course_name: str,
    topic_name: str,
    material_type: str,
    language: str,
    depth: str,
    context_text: str,
    source_map: Dict[str, Dict[str, Any]],
    personalization: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate grounded structured revision material JSON using LLM with RAG chunks.
    Falls back gracefully if LLM API is unavailable.
    """
    mat_title = MATERIAL_TYPE_TITLES.get(material_type, "Revision Material")
    full_title = f"{topic_name} — {mat_title}"

    lang_instruction = "Respond in clear English."
    if language in ("Hindi", "Hinglish"):
        lang_instruction = f"Respond in {language} language. Keep scientific symbols, equations, and mathematical variables accurate."

    depth_instruction = "Provide a standard depth review."
    if depth == "concise":
        depth_instruction = "Be very concise, using bullet points, short key takeaways, and brief definitions."
    elif depth == "detailed":
        depth_instruction = "Provide comprehensive, in-depth explanations with step-by-step details."

    reasons_str = "; ".join(personalization.get("reasons", []))
    emphasis_str = "; ".join(personalization.get("emphasis_rules", []))
    misconception_str = ""
    if personalization.get("misconception_callouts"):
        m_list = [f"- {m['title']}: {m['description']}" for m in personalization["misconception_callouts"]]
        misconception_str = "STUDENT MISCONCEPTION NOTES TO ADDRESS:\n" + "\n".join(m_list)

    sys_instruction = (
        "You are an expert AI Study Assistant on VIDYA-X AI. "
        "Generate a course-grounded, structured revision document based strictly on the provided course material.\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Base all facts, definitions, and claims strictly on the provided course sources [SOURCE_N].\n"
        "2. Include source citations [SOURCE_1], [SOURCE_2] in sections where appropriate.\n"
        "3. Do NOT invent fake facts or external unsupported claims.\n"
        "4. Output strictly valid JSON matching the specified schema.\n"
    )

    prompt = f"""{sys_instruction}
{lang_instruction}
{depth_instruction}

COURSE: {course_name}
TOPIC / SCOPE: {topic_name}
MATERIAL TYPE: {mat_title} ({material_type})
PERSONALIZATION CONTEXT: {reasons_str}
EMPHASIS: {emphasis_str}
{misconception_str}

SOURCE COURSE MATERIAL CONTEXT:
{context_text or "No specific course chunks retrieved."}

Output a JSON object matching this exact schema:
{{
  "title": "{full_title}",
  "material_type": "{material_type}",
  "language": "{language}",
  "depth": "{depth}",
  "overview": "Clear 2-3 sentence overview of this material grounded in sources.",
  "sections": [
    {{
      "heading": "Section Heading",
      "content": "Detailed explanatory text grounded in course sources.",
      "key_points": ["Key point 1", "Key point 2"],
      "citations": [{{"source_id": "SOURCE_1"}}]
    }}
  ],
  "comparison_matrix": [
    {{
      "concept_a": "Concept A",
      "concept_b": "Concept B",
      "distinction": "Key distinguishing feature",
      "citations": [{{"source_id": "SOURCE_1"}}]
    }}
  ],
  "self_check": [
    {{
      "question": "Quick self-check recall question",
      "answer": "Concise correct answer",
      "citations": [{{"source_id": "SOURCE_1"}}]
    }}
  ],
  "misconception_corrections": [
    {{
      "mistake_title": "Common Mistaken View",
      "correct_view": "Authoritative correct reasoning from course sources",
      "explanation": "Why the mistake happens and how to avoid it",
      "citations": [{{"source_id": "SOURCE_1"}}]
    }}
  ]
}}
"""

    try:
        raw_response = _call_gemini_api(prompt, system_instruction=sys_instruction, temperature=0.15)
        clean_text = raw_response.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(clean_text)
        if isinstance(data, dict) and "sections" in data:
            return data
    except Exception as exc:
        logger.warning(f"[REVISION GENERATION FALLBACK] LLM call failed or produced malformed output: {exc}")

    # Fallback offline generator grounded directly in context_text / source_map
    return _generate_fallback_revision_content(
        course_name=course_name,
        topic_name=topic_name,
        material_type=material_type,
        language=language,
        depth=depth,
        source_map=source_map,
        personalization=personalization,
    )


def _generate_fallback_revision_content(
    course_name: str,
    topic_name: str,
    material_type: str,
    language: str,
    depth: str,
    source_map: Dict[str, Dict[str, Any]],
    personalization: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Offline fallback generator creating clean, structured revision materials directly
    from retrieved source chunks without requiring an active external LLM key.
    """
    mat_title = MATERIAL_TYPE_TITLES.get(material_type, "Revision Guide")
    full_title = f"{topic_name} — {mat_title}"

    sources_keys = list(source_map.keys())
    first_source_id = sources_keys[0] if sources_keys else "SOURCE_1"

    sections = []
    chunk_list = list(source_map.values())

    if not chunk_list:
        sections.append({
            "heading": f"Overview of {topic_name}",
            "content": f"Review foundational definitions and core concepts for {topic_name} in {course_name}.",
            "key_points": [f"Focus on core principles of {topic_name}."],
            "citations": [{"source_id": first_source_id}],
        })
    else:
        for idx, chunk in enumerate(chunk_list[:4], 1):
            text = chunk.get("content", "").strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            heading = lines[0][:60] if lines else f"Key Concept {idx}"
            body = " ".join(lines[1:5]) if len(lines) > 1 else text[:250]
            s_id = f"SOURCE_{idx}"

            sections.append({
                "heading": f"{idx}. {heading}",
                "content": body or f"Key findings and course material details for {topic_name}.",
                "key_points": lines[:3] if lines else [f"Review core principles of {topic_name}."],
                "citations": [{"source_id": s_id}],
            })

    comparison_matrix = []
    if len(chunk_list) >= 2:
        comparison_matrix.append({
            "concept_a": "Primary Concept",
            "concept_b": "Secondary Concept",
            "distinction": "Refer to course text for variable definitions and distinct physical/logical properties.",
            "citations": [{"source_id": "SOURCE_1"}],
        })

    self_check = [
        {
            "question": f"What is the fundamental definition or rule of {topic_name}?",
            "answer": "Refer to the authoritative course sources provided in the reference section above.",
            "citations": [{"source_id": first_source_id}],
        }
    ]

    misconception_corrections = []
    for m in personalization.get("misconception_callouts", []):
        misconception_corrections.append({
            "mistake_title": m.get("title", "Common Misunderstanding"),
            "correct_view": m.get("description", "Refer to standard course definitions."),
            "explanation": "Always verify units, signs, and formula constraints before calculating.",
            "citations": [{"source_id": first_source_id}],
        })

    return {
        "title": full_title,
        "material_type": material_type,
        "language": language,
        "depth": depth,
        "overview": f"Summary and study notes for {topic_name} in {course_name}, synthesized from uploaded course materials.",
        "sections": sections,
        "comparison_matrix": comparison_matrix,
        "self_check": self_check,
        "misconception_corrections": misconception_corrections,
    }
