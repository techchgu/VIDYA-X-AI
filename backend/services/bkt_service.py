"""
VIDYA-X AI — Bayesian Knowledge Tracing (BKT) Service (Step 8)

Implements standard BKT for estimating student topic/concept mastery.

BKT Parameters (all configurable via environment variables):
  P(L0) = BKT_INITIAL_MASTERY  — initial probability of knowing (default 0.20)
  P(T)  = BKT_LEARNING_RATE    — probability of learning after an attempt (default 0.10)
  P(G)  = BKT_GUESS_RATE       — probability of guessing correctly (default 0.20)
  P(S)  = BKT_SLIP_RATE        — probability of slipping despite knowing (default 0.10)

BKT is a probabilistic estimate of knowledge, NOT a direct measurement.
"""

import os
from typing import Dict, Any


# ---------------------------------------------------------------------------
# Configurable BKT parameters (loaded from environment variables)
# ---------------------------------------------------------------------------

BKT_INITIAL_MASTERY = float(os.getenv("BKT_INITIAL_MASTERY", "0.20"))  # P(L0)
BKT_LEARNING_RATE   = float(os.getenv("BKT_LEARNING_RATE",   "0.10"))  # P(T)
BKT_GUESS_RATE      = float(os.getenv("BKT_GUESS_RATE",      "0.20"))  # P(G)
BKT_SLIP_RATE       = float(os.getenv("BKT_SLIP_RATE",       "0.10"))  # P(S)

MASTERY_THRESHOLD     = float(os.getenv("MASTERY_THRESHOLD",     "0.80"))  # >= 0.80 → Mastered
WEAK_TOPIC_THRESHOLD  = float(os.getenv("WEAK_TOPIC_THRESHOLD",  "0.50"))  # <  0.50 → Needs Review


# ---------------------------------------------------------------------------
# Core BKT update
# ---------------------------------------------------------------------------

def update_bkt(
    prior_mastery: float,
    is_correct: bool,
    p_learn: float = None,
    p_guess: float = None,
    p_slip: float = None,
) -> Dict[str, Any]:
    """
    Apply one BKT update step given the prior mastery probability and whether
    the student answered correctly.

    Steps:
      1. Compute posterior P(K | observation) using Bayes' theorem.
      2. Apply learning transition: P(K_next) = P(K_post) + (1 - P(K_post)) * P(T)
      3. Clamp result to [0.0, 1.0].

    Args:
        prior_mastery : P(K) before this observation, in [0.0, 1.0]
        is_correct    : True if the student answered correctly.
        p_learn       : P(T) — defaults to BKT_LEARNING_RATE
        p_guess       : P(G) — defaults to BKT_GUESS_RATE
        p_slip        : P(S) — defaults to BKT_SLIP_RATE

    Returns:
        dict with keys:
          prior_mastery      — the value before this call
          posterior_mastery  — Bayesian update before learning transition
          updated_mastery    — final value after learning transition (store this)
          is_correct         — echoed back for convenience
    """
    if p_learn is None:
        p_learn = BKT_LEARNING_RATE
    if p_guess is None:
        p_guess = BKT_GUESS_RATE
    if p_slip is None:
        p_slip = BKT_SLIP_RATE

    pk = float(prior_mastery)
    pk = max(0.0, min(1.0, pk))  # defensive clamp

    if is_correct:
        # P(K | correct) = P(K)*(1-P(S)) / [P(K)*(1-P(S)) + (1-P(K))*P(G)]
        numerator   = pk * (1.0 - p_slip)
        denominator = numerator + (1.0 - pk) * p_guess
    else:
        # P(K | incorrect) = P(K)*P(S) / [P(K)*P(S) + (1-P(K))*(1-P(G))]
        numerator   = pk * p_slip
        denominator = numerator + (1.0 - pk) * (1.0 - p_guess)

    # Guard against division-by-zero
    if denominator == 0.0:
        posterior = pk
    else:
        posterior = numerator / denominator

    # Apply learning transition
    updated = posterior + (1.0 - posterior) * p_learn

    # Clamp to [0.0, 1.0]
    updated   = max(0.0, min(1.0, updated))
    posterior = max(0.0, min(1.0, posterior))

    return {
        "prior_mastery":     round(pk, 6),
        "posterior_mastery": round(posterior, 6),
        "updated_mastery":   round(updated, 6),
        "is_correct":        is_correct,
    }


def update_bkt_with_evidence(
    prior_mastery: float,
    evidence: float,
    p_learn: float = None,
    p_guess: float = None,
    p_slip: float = None,
) -> Dict[str, Any]:
    """
    BKT update where evidence is a continuous score in [0.0, 1.0].

    Used for short-answer partial credit:
      evidence = 1.0  → fully correct (same as is_correct=True)
      evidence = 0.5  → partially correct
      evidence = 0.0  → incorrect (same as is_correct=False)

    Implementation (prototype):
      Blend the correct and incorrect BKT updates proportionally to evidence.
      This approximates weighted evidence without requiring IRT.

    Args:
        prior_mastery : current mastery probability
        evidence      : float in [0.0, 1.0]
        p_learn / p_guess / p_slip: BKT parameters

    Returns:
        Same structure as update_bkt().
    """
    evidence = max(0.0, min(1.0, float(evidence)))

    result_correct   = update_bkt(prior_mastery, True,  p_learn, p_guess, p_slip)
    result_incorrect = update_bkt(prior_mastery, False, p_learn, p_guess, p_slip)

    blended_updated   = evidence * result_correct["updated_mastery"]   + (1.0 - evidence) * result_incorrect["updated_mastery"]
    blended_posterior = evidence * result_correct["posterior_mastery"] + (1.0 - evidence) * result_incorrect["posterior_mastery"]

    blended_updated   = max(0.0, min(1.0, blended_updated))
    blended_posterior = max(0.0, min(1.0, blended_posterior))

    return {
        "prior_mastery":     round(float(prior_mastery), 6),
        "posterior_mastery": round(blended_posterior, 6),
        "updated_mastery":   round(blended_updated, 6),
        "is_correct":        evidence >= 0.5,
        "evidence":          round(evidence, 4),
    }


# ---------------------------------------------------------------------------
# Mastery state classification
# ---------------------------------------------------------------------------

def classify_mastery(mastery: float) -> str:
    """
    Convert a numeric mastery probability to a human-readable state label.

    Thresholds (configurable via MASTERY_THRESHOLD and WEAK_TOPIC_THRESHOLD):
      >= MASTERY_THRESHOLD    → 'Mastered'
      >= WEAK_TOPIC_THRESHOLD → 'Developing'
      <  WEAK_TOPIC_THRESHOLD → 'Needs Review'

    These are prototype thresholds and are NOT scientifically universal.
    """
    m = float(mastery)
    if m >= MASTERY_THRESHOLD:
        return "Mastered"
    if m >= WEAK_TOPIC_THRESHOLD:
        return "Developing"
    return "Needs Review"
