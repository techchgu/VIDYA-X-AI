"""
VIDYA-X AI — Flashcard Engine Service (Step 11)

Generates grounded flashcard decks, prevents near-duplicates via fingerprinting,
persists decks/cards with source citations, and records student card review ratings.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    Topic,
    Concept,
    FlashcardDeck,
    Flashcard,
    FlashcardReview,
)
from services.search_service import semantic_search
from services.llm_service import _call_gemini_api
from services.revision_validation_service import (
    extract_source_map_from_chunks,
    resolve_and_validate_citations,
)
from services.revision_personalization_service import build_personalization_plan

logger = logging.getLogger(__name__)

VALID_RATINGS = {"again", "hard", "good", "easy"}


def compute_card_fingerprint(front_text: str, card_type: str = "") -> str:
    """Compute normalized SHA-256 fingerprint of card front text for deduplication."""
    norm = f"{card_type.strip().lower()}:{front_text.strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def generate_flashcard_deck(
    db: Session,
    student_id: str,
    course_id: str,
    topic_id: Optional[str] = None,
    card_count: int = 10,
    language: str = "English",
    difficulty_mix: str = "balanced",
) -> Dict[str, Any]:
    """
    Generate a grounded flashcard deck for a student and course/topic.
    """
    card_count = max(3, min(30, card_count))

    # Resolve topic name
    topic_name = "General Course Knowledge"
    if topic_id:
        t = db.query(Topic).filter(Topic.id == topic_id, Topic.course_id == course_id).first()
        if t:
            topic_name = t.name

    # Retrieve RAG chunks
    query_str = topic_name
    chunks = semantic_search(db=db, course_id=course_id, query=query_str, top_k=6)
    source_map, context_text = extract_source_map_from_chunks(chunks)

    # Personalization plan
    personalization = build_personalization_plan(db, student_id, course_id, requested_topic_id=topic_id)

    deck_title = f"{topic_name} — Flashcards"

    # LLM Generation or Fallback
    raw_cards = _generate_raw_cards(
        topic_name=topic_name,
        card_count=card_count,
        language=language,
        difficulty_mix=difficulty_mix,
        context_text=context_text,
        source_map=source_map,
        personalization=personalization,
    )

    # Persist Deck
    now = datetime.now(timezone.utc)
    deck_id = str(uuid.uuid4()).replace("-", "")

    deck = FlashcardDeck(
        id=deck_id,
        student_id=student_id,
        course_id=course_id,
        topic_id=topic_id,
        title=deck_title,
        language=language,
        card_count=0,
        personalization_summary=personalization,
        created_at=now,
        updated_at=now,
    )
    db.add(deck)
    db.commit()

    # Deduplicate & Persist Cards
    seen_fingerprints = set()
    saved_cards = []

    for idx, c_raw in enumerate(raw_cards):
        front = c_raw.get("front", "").strip()
        back = c_raw.get("back", "").strip()
        if not front or not back:
            continue

        fp = compute_card_fingerprint(front, c_raw.get("card_type", "concept"))
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)

        # Resolve citations
        cits_raw = c_raw.get("citations", [])
        resolved_cits, _ = resolve_and_validate_citations(cits_raw, source_map)

        card_id = str(uuid.uuid4()).replace("-", "")
        card = Flashcard(
            id=card_id,
            deck_id=deck_id,
            front=front,
            back=back,
            explanation=c_raw.get("explanation"),
            difficulty=c_raw.get("difficulty", "medium"),
            card_type=c_raw.get("card_type", "concept_explanation"),
            topic_id=topic_id,
            concept_id=c_raw.get("concept_id"),
            citations=resolved_cits,
            fingerprint=fp,
            order_index=len(saved_cards) + 1,
            created_at=now,
        )
        db.add(card)
        saved_cards.append(card)

    deck.card_count = len(saved_cards)
    db.commit()

    return get_flashcard_deck(db, deck_id)


def get_flashcard_deck(db: Session, deck_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full detail of a flashcard deck with verified cards."""
    deck = db.query(FlashcardDeck).filter(FlashcardDeck.id == deck_id).first()
    if not deck:
        return None

    cards = db.query(Flashcard).filter(Flashcard.deck_id == deck_id).order_by(Flashcard.order_index.asc()).all()

    return {
        "deck_id": deck.id,
        "student_id": deck.student_id,
        "course_id": deck.course_id,
        "topic_id": deck.topic_id,
        "title": deck.title,
        "language": deck.language,
        "card_count": len(cards),
        "personalization_summary": deck.personalization_summary,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
        "cards": [
            {
                "card_id": c.id,
                "front": c.front,
                "back": c.back,
                "explanation": c.explanation,
                "difficulty": c.difficulty,
                "card_type": c.card_type,
                "topic_id": c.topic_id,
                "concept_id": c.concept_id,
                "citations": c.citations or [],
                "order_index": c.order_index,
            }
            for c in cards
        ],
    }


def record_card_review(
    db: Session,
    card_id: str,
    student_id: str,
    rating: str,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Record a student's recall rating for a flashcard."""
    rating_lower = (rating or "").strip().lower()
    if rating_lower not in VALID_RATINGS:
        return {"error": f"Invalid rating '{rating}'. Must be one of: {', '.join(VALID_RATINGS)}"}

    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        return {"error": f"Flashcard '{card_id}' not found"}

    deck = db.query(FlashcardDeck).filter(FlashcardDeck.id == card.deck_id).first()
    if not deck:
        return {"error": "Associated deck not found"}

    if deck.student_id != student_id:
        return {"error": "Deck does not belong to specified student"}

    now = datetime.now(timezone.utc)
    review_id = str(uuid.uuid4()).replace("-", "")

    rev = FlashcardReview(
        id=review_id,
        student_id=student_id,
        flashcard_id=card_id,
        deck_id=card.deck_id,
        rating=rating_lower,
        review_duration_ms=duration_ms,
        reviewed_at=now,
    )
    db.add(rev)
    db.commit()

    # Update flashcard spaced repetition scheduling state (Step 12)
    from services.spaced_repetition_service import update_flashcard_spaced_repetition
    updated_card = update_flashcard_spaced_repetition(db, card_id, rating_lower, now=now)

    return {
        "success": True,
        "review_id": review_id,
        "card_id": card_id,
        "deck_id": card.deck_id,
        "rating": rating_lower,
        "reviewed_at": now.isoformat(),
        "next_review_at": updated_card.next_review_at.isoformat() if (updated_card and updated_card.next_review_at) else None,
        "current_interval_days": updated_card.current_interval_days if updated_card else 0.0,
    }


def get_deck_reviews(db: Session, deck_id: str, student_id: str) -> List[Dict[str, Any]]:
    """Retrieve review history for a deck authorized by student ID."""
    deck = db.query(FlashcardDeck).filter(FlashcardDeck.id == deck_id).first()
    if not deck or deck.student_id != student_id:
        return []

    reviews = (
        db.query(FlashcardReview)
        .filter(FlashcardReview.deck_id == deck_id, FlashcardReview.student_id == student_id)
        .order_by(FlashcardReview.reviewed_at.desc())
        .all()
    )

    return [
        {
            "review_id": r.id,
            "card_id": r.flashcard_id,
            "rating": r.rating,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in reviews
    ]


def _generate_raw_cards(
    topic_name: str,
    card_count: int,
    language: str,
    difficulty_mix: str,
    context_text: str,
    source_map: Dict[str, Dict[str, Any]],
    personalization: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate raw flashcard dictionaries using Gemini LLM with RAG chunks, or fallback."""
    sys_instruction = (
        "You are an expert AI Study Companion on VIDYA-X AI. "
        "Generate grounded, active-recall flashcards strictly based on the provided course sources.\n\n"
        "RULES:\n"
        "1. Every card must test ONE clear concept or question.\n"
        "2. Ground every answer in the provided source chunks [SOURCE_N].\n"
        "3. Include citations [{'source_id': 'SOURCE_1'}].\n"
        "4. Return strictly valid JSON array of cards.\n"
    )

    prompt = f"""{sys_instruction}
Language: {language}
Topic: {topic_name}
Target Count: {card_count}

COURSE CONTEXT:
{context_text or "No course context."}

Output a JSON array of cards with this schema:
[
  {{
    "front": "Clear active-recall question or definition prompt?",
    "back": "Concise, precise answer grounded in sources.",
    "explanation": "Brief context or key insight.",
    "difficulty": "easy" | "medium" | "hard",
    "card_type": "definition" | "concept_explanation" | "formula" | "concept_comparison" | "misconception_correction",
    "citations": [{{"source_id": "SOURCE_1"}}]
  }}
]
"""

    try:
        raw_response = _call_gemini_api(prompt, system_instruction=sys_instruction, temperature=0.2)
        clean_text = raw_response.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(clean_text)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as exc:
        logger.warning(f"[FLASHCARD LLM FALLBACK] {exc}")

    # Fallback offline card generator from source chunks
    cards = []
    chunk_list = list(source_map.values())
    if not chunk_list:
        cards.append({
            "front": f"What is the core principle of {topic_name}?",
            "back": f"Review standard definitions for {topic_name} in uploaded course materials.",
            "explanation": "Fundamental concept definition.",
            "difficulty": "easy",
            "card_type": "concept_explanation",
            "citations": [{"source_id": "SOURCE_1"}],
        })
    else:
        for idx, chunk in enumerate(chunk_list[:card_count], 1):
            text = chunk.get("content", "").strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            prompt_q = lines[0][:80] if lines else f"Define Key Concept {idx} of {topic_name}."
            ans_b = " ".join(lines[1:4]) if len(lines) > 1 else text[:200]
            s_id = f"SOURCE_{idx}"

            cards.append({
                "front": f"What is the significance of: '{prompt_q}'?",
                "back": ans_b or f"Core concept detail for {topic_name}.",
                "explanation": f"Source document: {chunk.get('file_name', 'Course Material')}",
                "difficulty": "medium",
                "card_type": "definition" if idx % 2 == 1 else "concept_explanation",
                "citations": [{"source_id": s_id}],
            })

    # Add misconception card if present
    for m in personalization.get("misconception_callouts", [])[:2]:
        cards.append({
            "front": f"Common Error in {m.get('topic_name', topic_name)}: Why is '{m.get('title')}' incorrect?",
            "back": m.get("description", "Refer to standard course rules."),
            "explanation": "Correct reasoning derived from course assessment evidence.",
            "difficulty": "hard",
            "card_type": "misconception_correction",
            "citations": [{"source_id": "SOURCE_1"}],
        })

    return cards
