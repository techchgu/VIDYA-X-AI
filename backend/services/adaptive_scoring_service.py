"""
VIDYA-X AI — Adaptive Candidate Scoring Service (Step 9)

Scores and ranks candidate questions using a transparent, explainable weighted scoring model:
  adaptive_score =
      weakness_score * 0.35
    + difficulty_fit * 0.20
    + recent_failure_score * 0.15
    + prerequisite_score * 0.10
    + novelty_score * 0.10
    + diversity_score * 0.10
"""

import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import Question, QuizAttempt, Prerequisite, LearnerConceptMastery

# Configurable Thresholds (Step 6)
ADAPTIVE_WEAK_THRESHOLD = 0.50
ADAPTIVE_DEVELOPING_THRESHOLD = 0.80
ADAPTIVE_MASTERED_THRESHOLD = 0.80
ADAPTIVE_RECENT_ATTEMPTS = 5
ADAPTIVE_RECENT_WINDOW_HOURS = 72
ADAPTIVE_MASTERED_TOPIC_PROBABILITY = 0.10

# Weights for Candidate Scoring (Step 14)
WEIGHT_WEAKNESS = 0.35
WEIGHT_DIFFICULTY = 0.20
WEIGHT_RECENT_FAILURE = 0.15
WEIGHT_PREREQUISITE = 0.10
WEIGHT_NOVELTY = 0.10
WEIGHT_DIVERSITY = 0.10

ADAPTIVE_DEBUG = os.getenv("ADAPTIVE_DEBUG", "false").lower() in ("true", "1", "yes")


def calculate_target_difficulty(mastery: float) -> str:
    """
    Determine recommended target difficulty based on student mastery level (Step 10).
      mastery < 0.40       → Easy
      0.40 <= mastery < 0.65 → Easy / Medium
      0.65 <= mastery < 0.80 → Medium
      0.80 <= mastery < 0.90 → Medium / Hard
      mastery >= 0.90      → Hard
    """
    if mastery < 0.40:
        return "easy"
    elif mastery < 0.65:
        return "easy-medium"
    elif mastery < 0.80:
        return "medium"
    elif mastery < 0.90:
        return "medium-hard"
    else:
        return "hard"


def calculate_difficulty_fit(mastery: float, question_difficulty: str) -> float:
    """
    Score difficulty fit between 0.0 and 1.0 (Step 16).
    Does not force perfect matching if preferred difficulty isn't available.
    """
    q_diff = (question_difficulty or "medium").lower()

    if mastery < 0.40:
        if q_diff == "easy":
            return 1.0
        elif q_diff == "medium":
            return 0.6
        else:
            return 0.2
    elif mastery < 0.65:
        if q_diff in ("easy", "medium"):
            return 1.0 if q_diff == "easy" else 0.9
        else:
            return 0.4
    elif mastery < 0.80:
        if q_diff == "medium":
            return 1.0
        elif q_diff == "easy":
            return 0.7
        else:
            return 0.7
    elif mastery < 0.90:
        if q_diff in ("medium", "hard"):
            return 1.0 if q_diff == "hard" else 0.9
        else:
            return 0.4
    else:  # mastery >= 0.90
        if q_diff == "hard":
            return 1.0
        elif q_diff == "medium":
            return 0.7
        else:
            return 0.3


def calculate_weakness_score(mastery: float) -> float:
    """
    Weakness score is inversely proportional to mastery (Step 15).
    1.0 = completely weak (mastery = 0.0)
    0.0 = fully mastered (mastery = 1.0)
    """
    return max(0.0, min(1.0, 1.0 - mastery))


def calculate_recent_failure_score(
    concept_id: Optional[str],
    topic_id: Optional[str],
    recent_attempts: List[QuizAttempt],
) -> float:
    """
    Calculate recent failure priority based on the last N attempts for the concept/topic (Step 17).
    """
    if not recent_attempts:
        return 0.0

    relevant = []
    for att in recent_attempts:
        if concept_id and att.concept_id == concept_id:
            relevant.append(att)
        elif topic_id and att.topic_id == topic_id:
            relevant.append(att)

        if len(relevant) >= ADAPTIVE_RECENT_ATTEMPTS:
            break

    if not relevant:
        return 0.0

    incorrect_count = sum(1 for a in relevant if a.is_correct == 0)
    return float(incorrect_count) / len(relevant)


def calculate_prerequisite_priority(
    db: Session,
    course_id: str,
    concept_id: Optional[str],
    concept_mastery_map: Dict[str, float],
) -> float:
    """
    Calculate prerequisite importance score (Step 18 & 19).
    If concept_id is a prerequisite for a weak concept (mastery < 0.50),
    and its own mastery is low (< 0.80), boost priority.
    """
    if not concept_id:
        return 0.0

    prereqs = db.query(Prerequisite).filter(
        Prerequisite.course_id == course_id,
        Prerequisite.prerequisite_concept_id == concept_id,
    ).all()

    if not prereqs:
        return 0.0

    weak_dependents = 0
    for p in prereqs:
        target_mastery = concept_mastery_map.get(p.target_concept_id, 0.20)
        if target_mastery < ADAPTIVE_WEAK_THRESHOLD:
            weak_dependents += 1

    if weak_dependents > 0:
        own_mastery = concept_mastery_map.get(concept_id, 0.20)
        if own_mastery < ADAPTIVE_DEVELOPING_THRESHOLD:
            return min(1.0, 0.5 + 0.3 * weak_dependents)

    return 0.0


def calculate_novelty_score(
    question_id: str,
    attempt_counts: Dict[str, int],
) -> float:
    """
    Novelty score based on how many times the student has seen this question (Step 20).
      0 times → 1.0
      1 time  → 0.7
      2 times → 0.4
      3+ times → 0.1
    """
    seen_count = attempt_counts.get(question_id, 0)
    if seen_count == 0:
        return 1.0
    elif seen_count == 1:
        return 0.7
    elif seen_count == 2:
        return 0.4
    else:
        return 0.1


def calculate_diversity_score(
    question_type: str,
    recent_question_types: List[str],
) -> float:
    """
    Question-type diversity score (Step 21).
    Avoids selecting 5 consecutive MCQs if alternative question types exist.
    """
    if not recent_question_types:
        return 1.0

    # Look at last 3 question types
    last_three = recent_question_types[:3]
    if len(last_three) >= 2 and all(qt == question_type for qt in last_three):
        return 0.3  # Penalty for repetition
    elif last_three and last_three[0] == question_type:
        return 0.7

    return 1.0


def score_question_candidate(
    db: Session,
    question: Question,
    student_id: str,
    course_id: str,
    concept_mastery_map: Dict[str, float],
    topic_mastery_map: Dict[str, float],
    recent_attempts: List[QuizAttempt],
    attempt_counts: Dict[str, int],
    recent_question_types: List[str],
) -> Dict[str, Any]:
    """
    Compute total transparent weighted adaptive score for a candidate question.
    """
    # 1. Determine concept & topic mastery
    c_mastery = concept_mastery_map.get(question.concept_id or "") if question.concept_id else None
    t_mastery = topic_mastery_map.get(question.topic_id or "") if question.topic_id else None

    # Use concept mastery if available, else topic mastery, else initial default 0.20
    mastery = c_mastery if c_mastery is not None else (t_mastery if t_mastery is not None else 0.20)

    # 2. Compute individual components
    weakness = calculate_weakness_score(mastery)
    diff_fit = calculate_difficulty_fit(mastery, question.difficulty)
    recent_fail = calculate_recent_failure_score(question.concept_id, question.topic_id, recent_attempts)
    prereq_score = calculate_prerequisite_priority(db, course_id, question.concept_id, concept_mastery_map)
    novelty = calculate_novelty_score(question.id, attempt_counts)
    diversity = calculate_diversity_score(question.question_type, recent_question_types)

    # 3. Calculate weighted sum
    total_score = (
        weakness * WEIGHT_WEAKNESS
      + diff_fit * WEIGHT_DIFFICULTY
      + recent_fail * WEIGHT_RECENT_FAILURE
      + prereq_score * WEIGHT_PREREQUISITE
      + novelty * WEIGHT_NOVELTY
      + diversity * WEIGHT_DIVERSITY
    )

    reason = generate_selection_reason(mastery, recent_fail, prereq_score, question.difficulty)

    if ADAPTIVE_DEBUG:
        print(f"[ADAPTIVE DEBUG] Question {question.id} ({question.prompt[:30]}...):")
        print(f"  Weakness: {weakness:.2f}, DiffFit: {diff_fit:.2f}, RecentFail: {recent_fail:.2f}, "
              f"Prereq: {prereq_score:.2f}, Novelty: {novelty:.2f}, Diversity: {diversity:.2f}")
        print(f"  Final Score: {total_score:.4f}")

    return {
        "question": question,
        "score": round(total_score, 4),
        "mastery": round(mastery, 4),
        "reason": reason,
        "breakdown": {
            "weakness": round(weakness, 2),
            "difficulty_fit": round(diff_fit, 2),
            "recent_failure": round(recent_fail, 2),
            "prerequisite": round(prereq_score, 2),
            "novelty": round(novelty, 2),
            "diversity": round(diversity, 2),
        },
    }


def generate_selection_reason(
    mastery: float,
    recent_fail: float,
    prereq_score: float,
    difficulty: str,
) -> str:
    """
    Generate natural, user-understandable explanation for selecting this question (Step 29 & 50).
    Never exposes internal math formulas to the student.
    """
    if prereq_score > 0.5:
        return "Prerequisite foundational concept that needs to be strengthened first"
    elif recent_fail > 0.4:
        return "This concept needs review based on your recent practice answers"
    elif mastery < ADAPTIVE_WEAK_THRESHOLD:
        return "Low estimated mastery in this concept — targeted review"
    elif mastery < ADAPTIVE_DEVELOPING_THRESHOLD:
        return "Developing concept — practicing to build proficiency"
    elif mastery >= ADAPTIVE_MASTERED_THRESHOLD:
        return "Periodic review to reinforce and maintain mastery"
    else:
        return "Recommended practice based on your learning profile"
