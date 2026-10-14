"""
VIDYA-X AI — Spaced Repetition Engine Service (Step 12)

Implements spaced repetition scheduling algorithm for flashcards based on active recall ratings (again, hard, good, easy).
Updates card state (next_review_at, current_interval_days, review_count, last_reviewed_at, last_rating)
and retrieves due reviews for student study plans.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models import Flashcard, FlashcardDeck

logger = logging.getLogger(__name__)

# Default Spaced Repetition Configurations
SPACED_REPETITION_AGAIN_MINUTES = 10
SPACED_REPETITION_HARD_DAYS = 1.0
SPACED_REPETITION_GOOD_INITIAL_DAYS = 3.0
SPACED_REPETITION_EASY_INITIAL_DAYS = 7.0


def calculate_next_review(
    rating: str,
    current_interval_days: float = 0.0,
    review_count: int = 0,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calculate next review timestamp and interval based on recall rating.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    rating_clean = (rating or "good").strip().lower()
    prev_interval = max(0.0, float(current_interval_days or 0.0))
    count = int(review_count or 0)

    if rating_clean == "again":
        next_interval = 0.0
        next_review = now + timedelta(minutes=SPACED_REPETITION_AGAIN_MINUTES)
    elif rating_clean == "hard":
        next_interval = max(SPACED_REPETITION_HARD_DAYS, round(prev_interval * 1.2, 2))
        next_review = now + timedelta(days=next_interval)
    elif rating_clean == "easy":
        if count == 0:
            next_interval = SPACED_REPETITION_EASY_INITIAL_DAYS
        else:
            next_interval = max(SPACED_REPETITION_EASY_INITIAL_DAYS, round(prev_interval * 2.5, 2))
        next_review = now + timedelta(days=next_interval)
    else:
        # Default to "good"
        if count == 0:
            next_interval = SPACED_REPETITION_GOOD_INITIAL_DAYS
        else:
            next_interval = max(SPACED_REPETITION_GOOD_INITIAL_DAYS, round(prev_interval * 2.0, 2))
        next_review = now + timedelta(days=next_interval)

    new_count = count + 1

    return {
        "next_review_at": next_review,
        "next_interval_days": next_interval,
        "review_count": new_count,
        "last_rating": rating_clean,
        "last_reviewed_at": now,
    }


def update_flashcard_spaced_repetition(
    db: Session,
    card_id: str,
    rating: str,
    now: Optional[datetime] = None,
) -> Optional[Flashcard]:
    """
    Update a flashcard's spaced repetition scheduling state in the database.
    """
    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        return None

    calc = calculate_next_review(
        rating=rating,
        current_interval_days=card.current_interval_days or 0.0,
        review_count=card.review_count or 0,
        now=now,
    )

    card.next_review_at = calc["next_review_at"]
    card.current_interval_days = calc["next_interval_days"]
    card.review_count = calc["review_count"]
    card.last_reviewed_at = calc["last_reviewed_at"]
    card.last_rating = calc["last_rating"]

    db.commit()
    db.refresh(card)
    return card


def get_due_flashcards(
    db: Session,
    student_id: str,
    course_id: str,
    limit: int = 50,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve flashcards due for review for a given student and course.
    Includes both unreviewed cards (next_review_at is None) and cards whose next_review_at <= now.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    query = (
        db.query(Flashcard, FlashcardDeck)
        .join(FlashcardDeck, Flashcard.deck_id == FlashcardDeck.id)
        .filter(
            FlashcardDeck.student_id == student_id,
            FlashcardDeck.course_id == course_id,
            or_(
                Flashcard.next_review_at.is_(None),
                Flashcard.next_review_at <= now,
            ),
        )
        .order_by(Flashcard.next_review_at.asc().nullsfirst())
        .limit(limit)
    )

    results = query.all()
    due_cards = []
    for card, deck in results:
        is_overdue = card.next_review_at is not None and card.next_review_at < now
        due_cards.append({
            "card_id": card.id,
            "deck_id": deck.id,
            "deck_title": deck.title,
            "topic_id": card.topic_id,
            "concept_id": card.concept_id,
            "front": card.front,
            "back": card.back,
            "explanation": card.explanation,
            "difficulty": card.difficulty,
            "card_type": card.card_type,
            "citations": card.citations or [],
            "next_review_at": card.next_review_at.isoformat() if card.next_review_at else None,
            "current_interval_days": card.current_interval_days or 0.0,
            "review_count": card.review_count or 0,
            "last_reviewed_at": card.last_reviewed_at.isoformat() if card.last_reviewed_at else None,
            "last_rating": card.last_rating,
            "is_overdue": is_overdue,
            "due_status": "overdue" if is_overdue else ("due_now" if card.next_review_at else "new"),
        })

    return due_cards
