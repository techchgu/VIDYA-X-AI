"""
VIDYA-X AI — Vision Service (Step 14)
Interfaces with the configured vision-capable model (Gemini 1.5 Flash / Pro) to generate
structured, grounded descriptions of visual content extracted from course materials.
Never exposes credentials to the frontend.
"""

import base64
import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

VISION_MODEL = os.getenv("VISION_MODEL", "gemini-1.5-flash")
MAX_IMAGE_BYTES = int(os.getenv("VISION_MAX_IMAGE_BYTES", str(5 * 1024 * 1024)))  # 5 MB

_SYSTEM_PROMPT = """You are a precise educational visual-content analyzer for an AI tutor.
Describe the educational image strictly based on what is clearly visible.
Do not invent labels, values, axes, or relationships that are not present.
If an area is unclear, blurry, or unreadable, explicitly declare uncertainty.
Return ONLY valid JSON — no markdown code fences, no extra conversational text."""

_USER_PROMPT = """Analyze this visual material from an educational course.
Surrounding text context (if any): {context}

Return a JSON object conforming strictly to this structure:
{{
  "asset_type": "diagram" | "chart" | "equation" | "table" | "flowchart" | "scientific_illustration" | "annotated_image" | "process_diagram" | "slide" | "other_visual",
  "title": "Short descriptive title or null",
  "summary": "1 to 3 concise sentences describing what the visual conveys",
  "labels": [
    {{"text": "Extracted label", "confidence": 0.95}}
  ],
  "relationships": [
    {{"from": "Subject/Component", "relation": "connects_to / leads_to / contains", "to": "Object/Component"}}
  ],
  "equations": ["Equation representation if visible"],
  "chart_data": {{
    "x_axis": "Label and units or null",
    "y_axis": "Label and units or null",
    "trends": ["Observed trends or null"]
  }},
  "uncertain_regions": ["Description of unreadable or ambiguous regions"],
  "related_concepts": ["Educational concepts referenced in the visual"]
}}

Be accurate, factual, and conservative. Never fabricate data."""


def vision_available() -> bool:
    """Check if Gemini/Google API credentials are configured for vision processing."""
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def analyze_image(
    image_bytes: bytes,
    context_text: str = "",
    page: Optional[int] = None,
    slide: Optional[int] = None,
    timestamp_start: Optional[str] = None,
    timestamp_end: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send image bytes and contextual text to Gemini Vision model to produce structured description.

    Returns:
        dict with:
            structured_description (dict)
            visual_description (str for semantic indexing/search)
            model_used (str)
    """
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image size exceeds limit: {len(image_bytes)} bytes (max: {MAX_IMAGE_BYTES})")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY is not configured.")

    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("google-generativeai package is not installed.")

    context = (context_text or "").strip()[:2000]
    prompt = _USER_PROMPT.format(context=context or "(none provided)")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=VISION_MODEL,
        system_instruction=_SYSTEM_PROMPT,
    )

    img_part = {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(image_bytes).decode("utf-8"),
    }

    try:
        response = model.generate_content(
            [img_part, prompt],
            generation_config={"temperature": 0.1, "max_output_tokens": 1200},
        )
        raw_text = response.text.strip()
    except Exception as exc:
        logger.error(f"Gemini vision inference failed: {exc}")
        raise RuntimeError(f"Vision API call failed: {exc}")

    structured = _parse_vision_response(raw_text)
    structured["source_location"] = {
        "page": page,
        "slide": slide,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
    }

    plain_text = _build_plain_description(structured)

    return {
        "structured_description": structured,
        "visual_description": plain_text,
        "model_used": VISION_MODEL,
    }


def _parse_vision_response(raw: str) -> Dict[str, Any]:
    """Parse json cleanly from raw model output, tolerating fence blocks."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip())
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Parsed output is not a JSON dictionary")
        data.setdefault("asset_type", "other_visual")
        data.setdefault("title", None)
        data.setdefault("summary", "")
        data.setdefault("labels", [])
        data.setdefault("relationships", [])
        data.setdefault("equations", [])
        data.setdefault("chart_data", None)
        data.setdefault("uncertain_regions", [])
        data.setdefault("related_concepts", [])
        return data
    except Exception as exc:
        logger.warning(f"Vision JSON parse error: {exc}. Falling back to default wrapper.")
        return {
            "asset_type": "other_visual",
            "title": None,
            "summary": raw[:400] if raw else "Visual content extracted from course materials.",
            "labels": [],
            "relationships": [],
            "equations": [],
            "chart_data": None,
            "uncertain_regions": ["Raw vision response could not be parsed as structured JSON."],
            "related_concepts": [],
            "parse_error": str(exc),
        }


def _build_plain_description(structured: Dict[str, Any]) -> str:
    """Synthesize searchable text representation for embedding and semantic retrieval."""
    parts = []
    title = structured.get("title")
    if title:
        parts.append(f"Visual Title: {title}.")
    summary = structured.get("summary")
    if summary:
        parts.append(summary)
    labels = structured.get("labels", [])
    if labels:
        label_texts = [l["text"] for l in labels if isinstance(l, dict) and l.get("text")]
        if label_texts:
            parts.append(f"Labels: {', '.join(label_texts)}.")
    equations = structured.get("equations", [])
    if equations:
        eq_strs = [str(e) for e in equations if e]
        if eq_strs:
            parts.append(f"Equations: {'; '.join(eq_strs)}.")
    rels = structured.get("relationships", [])
    if rels:
        rel_strs = [
            f"{r.get('from','')} {r.get('relation','')} {r.get('to','')}"
            for r in rels
            if isinstance(r, dict) and r.get("from") and r.get("to")
        ]
        if rel_strs:
            parts.append(f"Relationships: {', '.join(rel_strs[:5])}.")
    chart = structured.get("chart_data")
    if isinstance(chart, dict):
        if chart.get("x_axis"):
            parts.append(f"X-Axis: {chart['x_axis']}.")
        if chart.get("y_axis"):
            parts.append(f"Y-Axis: {chart['y_axis']}.")
        if chart.get("trends") and isinstance(chart["trends"], list):
            parts.append(f"Trends: {'; '.join(str(t) for t in chart['trends'])}.")
    concepts = structured.get("related_concepts", [])
    if concepts and isinstance(concepts, list):
        parts.append(f"Key Concepts: {', '.join(str(c) for c in concepts)}.")

    return " ".join(parts).strip() or "Visual educational item."
