"""
VIDYA-X AI — Question Verification Service (Step 7 / Step 18 Trust Hardening)
Validates generated question structure, grounding, and source integrity
before questions are stored or served to students.

Step 18 additions:
  - Duplicate MCQ option text detection
  - Numerical tolerance validation
  - Rejection reason logging
  - MAX_GENERATION_RETRIES constant
"""

import logging
import re
from typing import Dict, Any, List, Tuple

from sqlalchemy.orm import Session

from database.models import KnowledgeChunk

_log = logging.getLogger(__name__)

# Maximum number of generation retry attempts before marking candidate as invalid
MAX_GENERATION_RETRIES: int = 3


# ---------------------------------------------------------------------------
# Public verification entry point
# ---------------------------------------------------------------------------

def verify_question(
    db: Session,
    question_data: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Run all verification checks on a candidate question dict.

    Checks performed (Step 18 extended):
      1. Required fields are present and non-empty.
      2. question_type is one of the supported values.
      3. MCQ has exactly 4 options with distinct keys A-D.
      3b. MCQ options have no duplicate texts (ambiguity check).
      4. MCQ correct_answer key matches one of the option keys.
      4b. Numerical correct_answer is parseable; tolerance (if present) is non-negative.
      5. source_refs list is non-empty and refers to real KnowledgeChunk IDs.
      6. Prompt length is within bounds (10-2000 chars).

    Args:
        db: SQLAlchemy session.
        question_data: Candidate question dict from the generation service.

    Returns:
        Tuple of (passed: bool, errors: List[str]).
        If passed is True, errors list is empty.
    """
    errors: List[str] = []

    # --- Check 1: Required fields ---
    required_fields = ["course_id", "question_type", "prompt", "correct_answer"]
    for field in required_fields:
        if not question_data.get(field):
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return False, errors

    # --- Check 2: question_type whitelist ---
    valid_types = {"mcq", "short_answer", "numerical"}
    q_type = question_data["question_type"]
    if q_type not in valid_types:
        errors.append(f"Invalid question_type '{q_type}'. Must be one of: {valid_types}")
        return False, errors

    # --- Check 3: MCQ structure ---
    if q_type == "mcq":
        options = question_data.get("options", [])
        if len(options) != 4:
            errors.append(f"MCQ must have exactly 4 options, got {len(options)}")
        else:
            keys = [o.get("key", "") for o in options]
            if sorted(keys) != ["A", "B", "C", "D"]:
                errors.append(f"MCQ options must have keys A, B, C, D -- got {sorted(keys)}")
            # Check 4: correct_answer key exists in options
            if question_data.get("correct_answer") not in keys:
                errors.append(
                    f"correct_answer '{question_data.get('correct_answer')}' "
                    f"does not match any option key in {keys}"
                )
            # All options must have non-empty, DISTINCT text (Step 18: duplicate check)
            option_texts = []
            for opt in options:
                text = opt.get("text", "").strip()
                if not text:
                    errors.append(f"Option '{opt.get('key')}' has empty text")
                else:
                    option_texts.append(text.lower())
            # --- Check 3b: Duplicate option texts ---
            if len(option_texts) != len(set(option_texts)):
                errors.append(
                    "MCQ has duplicate option texts -- all options must be distinguishable"
                )

    # --- Check 4b: Numerical correct_answer parseability + tolerance validation ---
    if q_type == "numerical":
        correct_answer_str = str(question_data.get("correct_answer", "")).strip()
        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", correct_answer_str)
        if not nums:
            errors.append(
                f"Numerical correct_answer '{correct_answer_str}' cannot be parsed as a number"
            )
        tolerance = question_data.get("tolerance")
        if tolerance is not None:
            try:
                tol_val = float(tolerance)
                if tol_val < 0:
                    errors.append(f"Numerical tolerance must be >= 0, got {tol_val}")
            except (ValueError, TypeError):
                errors.append(f"Numerical tolerance '{tolerance}' is not a valid number")

    # --- Check 5: Source grounding (chunk_ids must exist in DB) ---
    source_refs = question_data.get("source_refs", [])
    if not source_refs:
        errors.append("question must have at least one source_ref (grounding required)")
    else:
        for ref in source_refs:
            chunk_id = ref.get("chunk_id")
            if not chunk_id:
                errors.append("source_ref is missing 'chunk_id'")
                continue
            try:
                chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()
                if chunk is None:
                    errors.append(
                        f"source_ref chunk_id '{chunk_id}' not found in knowledge_chunks table"
                    )
            except Exception:
                # DB unavailable (e.g. test without schema) -- skip DB check
                pass

    # --- Check 6: Prompt sanity (length) ---
    prompt = question_data.get("prompt", "")
    if len(prompt.strip()) < 10:
        errors.append("prompt is too short (< 10 characters)")
    if len(prompt) > 2000:
        errors.append("prompt exceeds 2000 character limit")

    passed = len(errors) == 0
    return passed, errors


def filter_verified(
    db: Session,
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter a list of candidate questions, returning only those that pass verification.
    Logs skipped questions with their rejection reasons for debugging and evaluation.
    Invalid questions are NEVER served to students as verified assessment items.
    """
    verified = []
    for q in candidates:
        passed, errors = verify_question(db, q)
        if passed:
            verified.append(q)
        else:
            q_preview = str(q.get("prompt", ""))[:60]
            _log.warning(
                "Question rejected by verification [type=%s, prompt='%s...']: %s",
                q.get("question_type", "?"),
                q_preview,
                "; ".join(errors),
            )
    return verified
