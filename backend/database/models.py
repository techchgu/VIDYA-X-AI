"""
VIDYA-X AI — Database Schema Models (Step 5)
SQLAlchemy ORM models for courses, materials, extracted units, structured knowledge
(topics, concepts, definitions, relationships, prerequisites), and pgvector knowledge chunks.
"""

from datetime import datetime, timezone
import os
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .connection import Base

# Embedding dimension configured via environment variable (default: 384 for all-MiniLM-L6-v2)
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))


def utcnow():
    return datetime.now(timezone.utc)


class Course(Base):
    """Represents a student study course."""
    __tablename__ = "courses"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    materials = relationship("Material", back_populates="course", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="course", cascade="all, delete-orphan")
    chunks = relationship("KnowledgeChunk", back_populates="course", cascade="all, delete-orphan")


class Material(Base):
    """Represents an uploaded course material (.pdf, .ppt, .pptx, .mp4)."""
    __tablename__ = "materials"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    source_type = Column(String(32), nullable=False)  # pdf, ppt, video
    file_path = Column(String(512), nullable=True)
    status = Column(String(32), default="processed")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    course = relationship("Course", back_populates="materials")
    content_units = relationship("ContentUnit", back_populates="material", cascade="all, delete-orphan")


class ContentUnit(Base):
    """Represents an original source extraction unit (page, slide, or timestamped segment)."""
    __tablename__ = "content_units"

    id = Column(String(64), primary_key=True)
    material_id = Column(String(64), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    page = Column(Integer, nullable=True)
    slide = Column(Integer, nullable=True)
    timestamp_start = Column(String(32), nullable=True)
    timestamp_end = Column(String(32), nullable=True)
    unit_metadata = Column("metadata", JSON, nullable=True)

    # Relationships
    material = relationship("Material", back_populates="content_units")


class Topic(Base):
    """High-level subject module or chapter in a course."""
    __tablename__ = "topics"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)

    # Relationships
    course = relationship("Course", back_populates="topics")
    concepts = relationship("Concept", back_populates="topic", cascade="all, delete-orphan")


class Concept(Base):
    """Granular learning concept within a topic."""
    __tablename__ = "concepts"

    id = Column(String(64), primary_key=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    difficulty = Column(String(32), default="medium")  # initial content-level estimate

    # Relationships
    topic = relationship("Topic", back_populates="concepts")
    definitions = relationship("Definition", back_populates="concept", cascade="all, delete-orphan")


class Definition(Base):
    """Formal definition or formula belonging to a concept."""
    __tablename__ = "definitions"

    id = Column(String(64), primary_key=True)
    concept_id = Column(String(64), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    term = Column(String(255), nullable=False)
    definition = Column(Text, nullable=False)

    # Relationships
    concept = relationship("Concept", back_populates="definitions")


class Relationship(Base):
    """Directed semantic relationship edge connecting two concepts."""
    __tablename__ = "relationships"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    from_concept_id = Column(String(64), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False)  # prerequisite_of, depends_on, related_to, etc.
    to_concept_id = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, default=1.0)


class Prerequisite(Base):
    """Explicit prerequisite dependency edge between concepts."""
    __tablename__ = "prerequisites"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_concept_id = Column(String(64), nullable=False, index=True)
    target_concept_id = Column(String(64), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)


class KnowledgeChunk(Base):
    """
    Main semantic retrieval chunk embedded with pgvector.
    Preserves exact source origin and metadata for precise citations.
    """
    __tablename__ = "knowledge_chunks"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(String(64), ForeignKey("materials.id", ondelete="SET NULL"), nullable=True)
    content_unit_id = Column(String(64), nullable=True)
    content = Column(Text, nullable=False)
    chunk_type = Column(String(32), nullable=False)  # content_unit, definition, concept, etc.
    embedding = Column(Vector(EMBEDDING_DIMENSION))
    chunk_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    course = relationship("Course", back_populates="chunks")


# ---------------------------------------------------------------------------
# Step 7 — Adaptive Quiz Engine Models
# ---------------------------------------------------------------------------

class Question(Base):
    """
    A grounded question generated exclusively from course material chunks.
    Fingerprinting prevents duplicate storage of semantically identical prompts.
    """
    __tablename__ = "questions"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id = Column(String(64), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    question_type = Column(String(32), nullable=False)   # mcq | short_answer | numerical
    prompt = Column(Text, nullable=False)
    difficulty = Column(String(16), default="medium")    # easy | medium | hard
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    solution = Column(Text, nullable=True)               # step-by-step (numerical)
    source_refs = Column(JSON, nullable=True)            # list of {chunk_id, file_name, page, slide, …}
    fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(16), default="active")        # active | retired
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan")
    quiz_questions = relationship("QuizQuestion", back_populates="question", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="question", cascade="all, delete-orphan")
    usages = relationship("QuestionUsage", back_populates="question", cascade="all, delete-orphan")


class QuestionOption(Base):
    """MCQ answer option row (A–D). Only used for question_type='mcq'."""
    __tablename__ = "question_options"

    id = Column(String(64), primary_key=True)
    question_id = Column(String(64), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_key = Column(String(4), nullable=False)    # A, B, C, D
    option_text = Column(Text, nullable=False)
    is_correct = Column(Integer, default=0)           # 1 = correct, 0 = wrong

    # Relationships
    question = relationship("Question", back_populates="options")


class QuizSession(Base):
    """A single quiz attempt session for a student on a course."""
    __tablename__ = "quiz_sessions"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(64), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    mode = Column(String(32), default="practice")     # practice | exam | adaptive
    adaptive = Column(Integer, default=0)             # 1 = adaptive, 0 = standard
    current_question_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    quiz_questions = relationship("QuizQuestion", back_populates="session", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="session", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Step 9 — Adaptive Question Selection Evaluation Logs
# ---------------------------------------------------------------------------

class AdaptiveLog(Base):
    """
    Evaluation logging for adaptive question selection (Step 9).
    Logs every decision made by the adaptive engine for evaluation metrics.
    """
    __tablename__ = "adaptive_logs"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_id = Column(String(64), nullable=True, index=True)
    question_id = Column(String(64), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(64), nullable=True)
    concept_id = Column(String(64), nullable=True)
    mastery_before = Column(Float, nullable=True)
    mastery_after = Column(Float, nullable=True)
    selected_difficulty = Column(String(16), nullable=True)
    question_type = Column(String(32), nullable=True)
    selection_reason = Column(Text, nullable=True)
    adaptive_score = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)



class QuizQuestion(Base):
    """Join table that orders questions within a quiz session."""
    __tablename__ = "quiz_questions"

    id = Column(String(64), primary_key=True)
    quiz_session_id = Column(String(64), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(64), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, default=0)

    # Relationships
    session = relationship("QuizSession", back_populates="quiz_questions")
    question = relationship("Question", back_populates="quiz_questions")


class QuizAttempt(Base):
    """Records a student's single answer to one question inside a quiz session."""
    __tablename__ = "quiz_attempts"

    id = Column(String(64), primary_key=True)
    quiz_session_id = Column(String(64), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(64), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(String(64), nullable=True, index=True)
    topic_id = Column(String(64), nullable=True)
    concept_id = Column(String(64), nullable=True)
    question_type = Column(String(32), nullable=True)
    difficulty = Column(String(16), nullable=True)
    student_answer = Column(Text, nullable=True)
    is_correct = Column(Integer, nullable=True)       # 1 | 0 | None (unanswered)
    score = Column(Float, nullable=True)              # 0.0–1.0
    feedback = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    session = relationship("QuizSession", back_populates="attempts")
    question = relationship("Question", back_populates="attempts")


class QuestionUsage(Base):
    """Tracks every time a question is shown to a student (for deduplication across sessions)."""
    __tablename__ = "question_usage"

    id = Column(String(64), primary_key=True)
    question_id = Column(String(64), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(64), nullable=True, index=True)
    used_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    question = relationship("Question", back_populates="usages")


# ---------------------------------------------------------------------------
# Step 8 — Learner Model (BKT Mastery Tracking)
# ---------------------------------------------------------------------------

class LearnerTopicMastery(Base):
    """
    BKT-estimated mastery probability for a (student, course, topic) triplet.
    Updated after every verified quiz answer associated with this topic.

    mastery_probability is a Bayesian estimate in [0.0, 1.0].
    It is NOT a direct measurement of knowledge.
    """
    __tablename__ = "learner_topic_mastery"

    id = Column(String(64), primary_key=True)
    student_id           = Column(String(64), nullable=False, index=True)
    course_id            = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id             = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    mastery_probability  = Column(Float, default=0.20, nullable=False)
    attempt_count        = Column(Integer, default=0)
    correct_count        = Column(Integer, default=0)
    incorrect_count      = Column(Integer, default=0)
    last_attempt_at      = Column(DateTime(timezone=True), nullable=True)
    last_correct_at      = Column(DateTime(timezone=True), nullable=True)
    last_incorrect_at    = Column(DateTime(timezone=True), nullable=True)
    updated_at           = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LearnerConceptMastery(Base):
    """
    BKT-estimated mastery probability for a (student, course, concept) triplet.
    Concept-level granularity within a topic.
    """
    __tablename__ = "learner_concept_mastery"

    id = Column(String(64), primary_key=True)
    student_id           = Column(String(64), nullable=False, index=True)
    course_id            = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id           = Column(String(64), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id             = Column(String(64), nullable=True, index=True)
    mastery_probability  = Column(Float, default=0.20, nullable=False)
    attempt_count        = Column(Integer, default=0)
    correct_count        = Column(Integer, default=0)
    incorrect_count      = Column(Integer, default=0)
    last_attempt_at      = Column(DateTime(timezone=True), nullable=True)
    updated_at           = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Step 10 — Misconception Detection & Personalized Remediation Models
# ---------------------------------------------------------------------------

class MisconceptionRecord(Base):
    """
    Tracks recurring or suspected student misunderstandings for a (student, course, concept) triplet.
    Supports lifecycle: suspected -> supported -> under_review -> improving -> resolved.
    """
    __tablename__ = "misconception_records"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id = Column(String(64), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    misconception_code = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    evidence_summary = Column(Text, nullable=True)
    confidence = Column(Float, default=0.50, nullable=False)
    status = Column(String(32), default="suspected", nullable=False, index=True)  # suspected | supported | under_review | improving | resolved
    first_detected_at = Column(DateTime(timezone=True), default=utcnow)
    last_observed_at = Column(DateTime(timezone=True), default=utcnow)
    occurrence_count = Column(Integer, default=1)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    evidence = relationship("MisconceptionEvidence", back_populates="misconception", cascade="all, delete-orphan")


class MisconceptionEvidence(Base):
    """
    Individual evidence link associating a specific QuizAttempt with a MisconceptionRecord.
    Idempotent: unique constraint on (misconception_id, attempt_id).
    """
    __tablename__ = "misconception_evidence"
    __table_args__ = (
        UniqueConstraint("misconception_id", "attempt_id", name="uq_misconception_attempt"),
    )

    id = Column(String(64), primary_key=True)
    misconception_id = Column(String(64), ForeignKey("misconception_records.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id = Column(String(64), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(64), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    student_answer_summary = Column(Text, nullable=True)
    expected_answer_summary = Column(Text, nullable=True)
    evidence_type = Column(String(64), nullable=False)  # numerical_mismatch | missing_units | distractor_mapping | llm_analysis | rubric_omission
    evidence_strength = Column(Float, default=0.50)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    misconception = relationship("MisconceptionRecord", back_populates="evidence")


class RemediationSession(Base):
    """
    A personalized remediation session created to address a student's misconception or weak concept.
    """
    __tablename__ = "remediation_sessions"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    concept_id = Column(String(64), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    misconception_id = Column(String(64), ForeignKey("misconception_records.id", ondelete="SET NULL"), nullable=True)
    session_type = Column(String(32), default="targeted_remediation")
    status = Column(String(32), default="active")  # active | completed | abandoned
    explanation = Column(Text, nullable=False)
    source_refs = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    activities = relationship("RemediationActivity", back_populates="session", cascade="all, delete-orphan")


class RemediationActivity(Base):
    """
    Sub-activity within a remediation session (worked example, comparison, self-check, practice question).
    """
    __tablename__ = "remediation_activities"

    id = Column(String(64), primary_key=True)
    remediation_session_id = Column(String(64), ForeignKey("remediation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type = Column(String(32), nullable=False)  # worked_example | comparison | self_check | practice_question
    activity_data = Column(JSON, nullable=False)
    order_index = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("RemediationSession", back_populates="activities")


# ---------------------------------------------------------------------------
# Step 11 — Personalized Revision Materials & Flashcard Engine Models
# ---------------------------------------------------------------------------

class RevisionMaterial(Base):
    """
    Generated personalized revision resource (notes, study guide, formula sheet, checklist, etc.).
    Grounded in course knowledge chunks with verified source citations.
    """
    __tablename__ = "revision_materials"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    material_type = Column(String(64), nullable=False, index=True)  # topic_summary | revision_notes | exam_revision_sheet | formula_sheet | concept_comparison | definitions_terminology | quick_checklist | weak_topic_study_guide
    language = Column(String(32), default="English", nullable=False)
    depth = Column(String(32), default="standard", nullable=False)   # concise | standard | detailed
    grounded = Column(Integer, default=1, nullable=False)           # 1 = grounded, 0 = fallback
    content_json = Column(JSON, nullable=False)
    personalization_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    sources = relationship("RevisionMaterialSource", back_populates="revision_material", cascade="all, delete-orphan")


class RevisionMaterialSource(Base):
    """
    Source chunk citation associated with a RevisionMaterial.
    """
    __tablename__ = "revision_material_sources"

    id = Column(String(64), primary_key=True)
    revision_material_id = Column(String(64), ForeignKey("revision_materials.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=True)
    file_name = Column(String(255), nullable=True)
    source_type = Column(String(64), nullable=True)
    page = Column(Integer, nullable=True)
    slide = Column(Integer, nullable=True)
    timestamp_start = Column(String(32), nullable=True)
    timestamp_end = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    revision_material = relationship("RevisionMaterial", back_populates="sources")


class FlashcardDeck(Base):
    """
    A generated flashcard deck for a student and course/topic.
    """
    __tablename__ = "flashcard_decks"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    language = Column(String(32), default="English", nullable=False)
    card_count = Column(Integer, default=0)
    personalization_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    cards = relationship("Flashcard", back_populates="deck", cascade="all, delete-orphan")


class Flashcard(Base):
    """
    Single flashcard in a deck with front/back text, explanation, difficulty, type, and source citations.
    """
    __tablename__ = "flashcards"

    id = Column(String(64), primary_key=True)
    deck_id = Column(String(64), ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=False, index=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    difficulty = Column(String(16), default="medium")  # easy | medium | hard
    card_type = Column(String(32), default="concept")  # definition | concept_explanation | formula | concept_comparison | cause_effect | process_sequence | misconception_correction | worked_example
    topic_id = Column(String(64), nullable=True)
    concept_id = Column(String(64), nullable=True)
    citations = Column(JSON, nullable=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Spaced repetition scheduling state (Step 12)
    next_review_at = Column(DateTime(timezone=True), nullable=True, index=True)
    current_interval_days = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    last_rating = Column(String(16), nullable=True)

    # Relationships
    deck = relationship("FlashcardDeck", back_populates="cards")
    reviews = relationship("FlashcardReview", back_populates="flashcard", cascade="all, delete-orphan")


class FlashcardReview(Base):
    """
    Record of a student reviewing a flashcard with recall rating (again, hard, good, easy).
    """
    __tablename__ = "flashcard_reviews"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    flashcard_id = Column(String(64), ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True)
    deck_id = Column(String(64), ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(String(16), nullable=False)  # again | hard | good | easy
    review_duration_ms = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    flashcard = relationship("Flashcard", back_populates="reviews")


# ---------------------------------------------------------------------------
# Step 12 — Intelligent Study Planner & Spaced Repetition Models
# ---------------------------------------------------------------------------

class StudentStudyPreferences(Base):
    """
    Stores study plan preferences per student and course.
    """
    __tablename__ = "student_study_preferences"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course_prefs"),
    )

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    daily_minutes_budget = Column(Integer, default=45, nullable=False)
    exam_date = Column(DateTime(timezone=True), nullable=True)
    preferred_session_minutes = Column(Integer, default=15, nullable=False)
    selected_topics = Column(JSON, nullable=True)
    unavailable_dates = Column(JSON, nullable=True)  # list of YYYY-MM-DD
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StudyPlan(Base):
    """
    A personalized 7- or 14-day study plan generated for a student and course.
    """
    __tablename__ = "study_plans"

    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    exam_date = Column(DateTime(timezone=True), nullable=True)
    daily_minutes_budget = Column(Integer, default=45, nullable=False)
    status = Column(String(32), default="active", nullable=False, index=True)  # active | completed | archived
    plan_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    days = relationship("StudyPlanDay", back_populates="plan", cascade="all, delete-orphan")


class StudyPlanDay(Base):
    """
    A scheduled day within a StudyPlan.
    """
    __tablename__ = "study_plan_days"

    id = Column(String(64), primary_key=True)
    study_plan_id = Column(String(64), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_date = Column(String(32), nullable=False, index=True)  # YYYY-MM-DD
    planned_minutes = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="pending", nullable=False)   # pending | completed | partial | skipped
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    plan = relationship("StudyPlan", back_populates="days")
    tasks = relationship("StudyPlanTask", back_populates="day", cascade="all, delete-orphan")


class StudyPlanTask(Base):
    """
    A single study task scheduled for a specific day.
    """
    __tablename__ = "study_plan_tasks"

    id = Column(String(64), primary_key=True)
    study_plan_day_id = Column(String(64), ForeignKey("study_plan_days.id", ondelete="CASCADE"), nullable=False, index=True)
    task_type = Column(String(64), nullable=False, index=True)  # flashcard_review | weak_topic_revision | revision_material_read | adaptive_quiz | remediation_activity | prerequisite_review | mixed_practice | self_assessment
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    topic_id = Column(String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id = Column(String(64), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    resource_id = Column(String(64), nullable=True)
    resource_type = Column(String(64), nullable=True)  # flashcard_deck | revision_material | remediation_session | quiz
    estimated_minutes = Column(Integer, default=15, nullable=False)
    actual_minutes = Column(Integer, nullable=True)
    priority_score = Column(Float, default=0.0, nullable=False)
    priority_level = Column(String(16), default="medium", nullable=False)  # high | medium | low
    priority_reason = Column(Text, nullable=True)
    status = Column(String(32), default="pending", nullable=False, index=True)  # pending | in_progress | completed | skipped | rescheduled | cancelled
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completion_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    day = relationship("StudyPlanDay", back_populates="tasks")





# ---------------------------------------------------------------------------
# Step 14 — Visual Assets & Multimodal Understanding Models
# ---------------------------------------------------------------------------

class VisualAsset(Base):
    """
    Stores metadata and AI-generated descriptions for visual content extracted
    from PDFs, PowerPoint slides, and video frames.
    Asset types: embedded_image, rendered_pdf_page, rendered_slide, video_frame,
    diagram, chart, equation, table, other_visual.
    """
    __tablename__ = "visual_assets"

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(String(64), ForeignKey("materials.id", ondelete="CASCADE"), nullable=True, index=True)
    content_unit_id = Column(String(64), nullable=True, index=True)
    source_file_name = Column(String(255), nullable=False)
    source_type = Column(String(32), nullable=False)  # pdf | ppt | video
    asset_type = Column(String(64), nullable=False)   # embedded_image | rendered_pdf_page | rendered_slide | video_frame | diagram | chart | equation | table | other_visual
    page_number = Column(Integer, nullable=True)
    slide_number = Column(Integer, nullable=True)
    timestamp_start = Column(String(32), nullable=True)
    timestamp_end = Column(String(32), nullable=True)
    image_path = Column(String(512), nullable=True)   # server-side path only, never exposed raw to clients
    visual_description = Column(Text, nullable=True)  # retrievable plain-text description
    structured_description = Column(JSON, nullable=True)  # rich structured JSON representation
    processing_status = Column(String(32), default="pending", nullable=False, index=True)  # pending | processing | completed | failed | skipped
    processing_error = Column(Text, nullable=True)
    content_fingerprint = Column(String(64), nullable=True, index=True)  # SHA-256 for deduplication
    knowledge_chunk_id = Column(String(64), nullable=True)  # linked knowledge chunk id
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    material = relationship("Material")
    course = relationship("Course")
