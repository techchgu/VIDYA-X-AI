"""
VIDYA-X AI - Services Package
Provides file persistence, knowledge structuring, database ingestion, vector embeddings,
semantic search, knowledge graph, adaptive quiz, and BKT learner model services.
"""

from .file_service import (
    save_uploaded_file,
    save_extraction_result,
    sanitize_filename,
    ensure_directories,
    get_file_extension,
    generate_file_id,
    ALLOWED_EXTENSIONS,
    UPLOAD_DIR,
    EXTRACTED_DIR,
)
from .embedding_service import generate_embedding, generate_embeddings
from .llm_service import extract_structured_knowledge
from .knowledge_service import ingest_file_knowledge
from .search_service import semantic_search
from .graph_service import get_concept_graph, get_concept_details
from .question_service import (
    compute_fingerprint,
    question_exists,
    store_question,
    get_question_by_id,
    get_questions_for_course,
    record_question_result,
)
from .question_generation_service import generate_questions
from .question_verification_service import verify_question, filter_verified
from .quiz_service import create_quiz, get_quiz, submit_answer, get_quiz_result

# Step 8 — Learner Model & BKT
from .bkt_service import (
    update_bkt,
    update_bkt_with_evidence,
    classify_mastery,
    BKT_INITIAL_MASTERY,
    BKT_LEARNING_RATE,
    BKT_GUESS_RATE,
    BKT_SLIP_RATE,
    MASTERY_THRESHOLD,
    WEAK_TOPIC_THRESHOLD,
)
from .learner_model_service import update_learner_after_attempt
from .mastery_service import (
    get_topic_mastery,
    get_concept_mastery,
    get_all_mastery,
    get_weak_topics,
    get_strong_topics,
    get_concept_mastery_list,
    reset_learner_state,
    has_learner_history,
)

# Step 9 — Adaptive Question Selection & Personalization
from .candidate_service import (
    get_candidate_questions,
    get_recently_used_questions,
    filter_and_relax_candidates,
    get_recent_attempts_history,
)
from .adaptive_scoring_service import (
    score_question_candidate,
    calculate_target_difficulty,
    calculate_difficulty_fit,
    calculate_weakness_score,
    calculate_recent_failure_score,
    calculate_prerequisite_priority,
    calculate_novelty_score,
    calculate_diversity_score,
    generate_selection_reason,
    ADAPTIVE_WEAK_THRESHOLD,
    ADAPTIVE_DEVELOPING_THRESHOLD,
    ADAPTIVE_MASTERED_THRESHOLD,
)
from .adaptive_service import (
    get_next_question,
    create_adaptive_quiz,
    get_adaptive_next_question_for_session,
)
from .personalization_service import get_personalized_recommendations

# Step 10 — Misconception Detection & Personalized Remediation
from .misconception_detection_service import run_deterministic_checks, analyze_attempt_with_llm
from .misconception_service import (
    detect_misconceptions,
    get_student_misconceptions,
    get_misconception_by_id,
)
from .remediation_service import create_remediation
from .remediation_tracking_service import (
    get_remediation_session,
    get_student_remediations,
    complete_remediation_activity,
    evaluate_remediation_outcome,
)

# Step 11 — Personalized Revision Materials & Flashcard Engine
from .revision_personalization_service import build_personalization_plan
from .revision_validation_service import validate_topic_and_course, resolve_and_validate_citations
from .revision_generation_service import generate_revision_content
from .flashcard_service import (
    generate_flashcard_deck,
    get_flashcard_deck,
    record_card_review,
    get_deck_reviews,
    compute_card_fingerprint,
)
from .revision_service import (
    generate_revision_material,
    get_revision_material,
    get_student_revision_materials,
    delete_revision_material,
    get_student_flashcard_decks,
    delete_flashcard_deck,
)

# Step 12 — Intelligent Study Planner & Spaced Repetition Engine
from .spaced_repetition_service import (
    calculate_next_review,
    update_flashcard_spaced_repetition,
    get_due_flashcards,
)
from .prioritization_service import calculate_topic_priorities
from .study_planner_service import (
    get_or_create_preferences,
    generate_study_plan,
    get_active_study_plan,
    get_today_tasks,
)
from .study_plan_tracking_service import update_task_status, complete_task
from .exam_readiness_service import evaluate_exam_readiness

# Step 14 — Multimodal Course Understanding & Visual Intelligence
from .vision_service import analyze_image, vision_available
from .visual_extraction_service import (
    extract_images_from_pdf,
    extract_images_from_pptx,
    extract_frames_from_video,
)
from .visual_indexing_service import (
    process_material_visuals,
    get_material_visual_status,
)
from .visual_retrieval_service import (
    search_visual_descriptions,
    list_course_visual_assets,
    get_visual_asset_detail,
)

__all__ = [
    # Step 3 — File & extraction
    "save_uploaded_file",
    "save_extraction_result",
    "sanitize_filename",
    "ensure_directories",
    "get_file_extension",
    "generate_file_id",
    "ALLOWED_EXTENSIONS",
    "UPLOAD_DIR",
    "EXTRACTED_DIR",
    # Step 5 — Knowledge base
    "generate_embedding",
    "generate_embeddings",
    "extract_structured_knowledge",
    "ingest_file_knowledge",
    "semantic_search",
    "get_concept_graph",
    "get_concept_details",
    # Step 7 — Quiz engine
    "compute_fingerprint",
    "question_exists",
    "store_question",
    "get_question_by_id",
    "get_questions_for_course",
    "record_question_result",
    "generate_questions",
    "verify_question",
    "filter_verified",
    "create_quiz",
    "get_quiz",
    "submit_answer",
    "get_quiz_result",
    # Step 8 — Learner model & BKT
    "update_bkt",
    "update_bkt_with_evidence",
    "classify_mastery",
    "BKT_INITIAL_MASTERY",
    "BKT_LEARNING_RATE",
    "BKT_GUESS_RATE",
    "BKT_SLIP_RATE",
    "MASTERY_THRESHOLD",
    "WEAK_TOPIC_THRESHOLD",
    "update_learner_after_attempt",
    "get_topic_mastery",
    "get_concept_mastery",
    "get_all_mastery",
    "get_weak_topics",
    "get_strong_topics",
    "get_concept_mastery_list",
    "reset_learner_state",
    "has_learner_history",
    # Step 9 — Adaptive & Personalization
    "get_candidate_questions",
    "get_recently_used_questions",
    "filter_and_relax_candidates",
    "get_recent_attempts_history",
    "score_question_candidate",
    "calculate_target_difficulty",
    "calculate_difficulty_fit",
    "calculate_weakness_score",
    "calculate_recent_failure_score",
    "calculate_prerequisite_priority",
    "calculate_novelty_score",
    "calculate_diversity_score",
    "generate_selection_reason",
    "get_next_question",
    "create_adaptive_quiz",
    "get_adaptive_next_question_for_session",
    "get_personalized_recommendations",
    # Step 10 — Misconception & Remediation
    "run_deterministic_checks",
    "analyze_attempt_with_llm",
    "detect_misconceptions",
    "get_student_misconceptions",
    "get_misconception_by_id",
    "create_remediation",
    "get_remediation_session",
    "get_student_remediations",
    "complete_remediation_activity",
    "evaluate_remediation_outcome",
    # Step 11 — Revision & Flashcards
    "build_personalization_plan",
    "validate_topic_and_course",
    "resolve_and_validate_citations",
    "generate_revision_content",
    "generate_flashcard_deck",
    "get_flashcard_deck",
    "record_card_review",
    "get_deck_reviews",
    "compute_card_fingerprint",
    "generate_revision_material",
    "get_revision_material",
    "get_student_revision_materials",
    "delete_revision_material",
    "get_student_flashcard_decks",
    "delete_flashcard_deck",
    # Step 12 — Study Planner & Spaced Repetition
    "calculate_next_review",
    "update_flashcard_spaced_repetition",
    "get_due_flashcards",
    "calculate_topic_priorities",
    "get_or_create_preferences",
    "generate_study_plan",
    "get_active_study_plan",
    "get_today_tasks",
    "update_task_status",
    "complete_task",
    "evaluate_exam_readiness",
    # Step 14 — Multimodal & Visual Intelligence
    "analyze_image",
    "vision_available",
    "extract_images_from_pdf",
    "extract_images_from_pptx",
    "extract_frames_from_video",
    "process_material_visuals",
    "get_material_visual_status",
    "search_visual_descriptions",
    "list_course_visual_assets",
    "get_visual_asset_detail",
    # Step 15 — Grounded AI Tutor
    "answer_student_question",
]

# Step 15 — Grounded AI Tutor
from .tutor_service import answer_student_question



