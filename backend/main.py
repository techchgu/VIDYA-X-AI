"""
VIDYA-X AI — Multimodal AI Tutor Backend
FastAPI application providing:
  - Step 3: Multimodal content extraction (PDF / PPT / MP4)
  - Step 5: Knowledge ingestion, semantic search, concept graph
  - Step 7: Adaptive quiz generation and evaluation
"""

from datetime import datetime, timezone
import os
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from processors import process_pdf, process_ppt, process_video
from services import (
    ensure_directories,
    get_file_extension,
    save_uploaded_file,
    save_extraction_result,
    ALLOWED_EXTENSIONS,
    ingest_file_knowledge,
    semantic_search,
    get_concept_graph,
    get_concept_details,
    generate_questions,
    create_quiz,
    get_quiz,
    submit_answer,
    get_quiz_result,
    generate_revision_material,
    get_revision_material,
    get_student_revision_materials,
    delete_revision_material,
    generate_flashcard_deck,
    get_flashcard_deck,
    record_card_review,
    get_deck_reviews,
    get_student_flashcard_decks,
    delete_flashcard_deck,
    process_material_visuals,
    get_material_visual_status,
    search_visual_descriptions,
    list_course_visual_assets,
    get_visual_asset_detail,
    vision_available,
    answer_student_question,
)
from database.connection import get_db

# Initialize storage folders
from config import config
config.ensure_storage_directories()
ensure_directories()

# Initialize FastAPI application
app = FastAPI(
    title="VIDYA-X AI Backend",
    description="Course-Aware, Adaptive & Multimodal AI Tutor",
    version=config.VERSION,
)

# ---------------------------------------------------------------------------
# CORS Configuration (Production Hardened)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True if config.CORS_ORIGINS != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# System & Health Probes (Step 16 Production)
# ===========================================================================

@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
async def health_check():
    """Basic liveness probe — verifies HTTP process is serving."""
    return {
        "status": "ok",
        "service": "VIDYA-X AI Backend",
        "version": config.VERSION,
        "environment": config.APP_ENV,
    }


@app.get("/health/ready", tags=["System"])
@app.get("/api/health/ready", tags=["System"])
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe — verifies database connectivity and schema availability.
    Returns HTTP 503 if database cannot execute query.
    """
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(exc)[:200],
            },
        )

    return {
        "status": "ready",
        "database": db_status,
        "version": config.VERSION,
        "storage": "writable" if config.UPLOAD_DIR.exists() else "unmounted",
    }


@app.get("/health/ai", tags=["System"])
@app.get("/api/health/ai", tags=["System"])
async def ai_provider_check():
    """
    Diagnostic status of AI model providers without exposing secrets.
    """
    return {
        "status": "ok",
        "embedding_provider": config.EMBEDDING_PROVIDER,
        "embedding_model": config.EMBEDDING_MODEL,
        "vision_provider": "gemini" if config.HAS_GEMINI_KEY else "local_fallback",
        "vision_model": config.VISION_MODEL,
        "cloud_llm_ready": config.HAS_GEMINI_KEY,
        "demo_mode_allowed": config.DEMO_MODE_ENABLED,
    }


# ===========================================================================
# Step 3 — Multimodal Upload & Extraction
# ===========================================================================

@app.post("/api/upload", tags=["Course Materials"])
async def upload_material(
    file: UploadFile = File(...),
    course_name: str = Form("General"),
):
    """
    Accept an uploaded course material (.pdf, .ppt, .pptx, .mp4),
    run the specialized content processor, and persist structured extraction.
    """
    if not file.filename:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "No file was uploaded or filename is missing."},
        )

    ext = get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": f"Unsupported file type '{ext}'. Supported formats: PDF, PPT, PPTX, MP4.",
            },
        )

    try:
        content = await file.read()
        if not content:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": "Uploaded file is empty."},
            )
        max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "success": False,
                    "error": f"File exceeds maximum upload size limit of {config.MAX_UPLOAD_SIZE_MB}MB.",
                },
            )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Failed to read uploaded file: {str(exc)}"},
        )

    from services.file_service import generate_file_id
    file_id = generate_file_id()

    try:
        clean_name, saved_path = save_uploaded_file(content, file.filename, file_id)
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Failed to save file to storage: {str(exc)}"},
        )

    source_type = ""
    units = []

    try:
        if ext == ".pdf":
            source_type = "pdf"
            units = process_pdf(saved_path, file_id, clean_name)
        elif ext in {".ppt", ".pptx"}:
            source_type = "ppt"
            units = process_ppt(saved_path, file_id, clean_name)
        elif ext == ".mp4":
            source_type = "video"
            units = process_video(saved_path, file_id, clean_name)
    except (ValueError, RuntimeError) as proc_err:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "file_id": file_id, "error": str(proc_err)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "file_id": file_id, "error": f"Extraction failed: {str(exc)}"},
        )

    extraction_payload = {
        "file_id": file_id,
        "file_name": clean_name,
        "course_name": course_name.strip() or "General",
        "source_type": source_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "units": units,
    }

    try:
        extraction_file = save_extraction_result(extraction_payload, file_id)
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Failed to write extraction file: {str(exc)}"},
        )

    return {
        "success": True,
        "file_id": file_id,
        "file_name": clean_name,
        "source_type": source_type,
        "units_extracted": len(units),
        "extraction_file": extraction_file,
    }


# ===========================================================================
# Step 5 — Knowledge Ingestion, Semantic Search & Concept Graph
# ===========================================================================

@app.post("/api/knowledge/ingest/{file_id}", tags=["Knowledge Base"])
async def ingest_knowledge(
    file_id: str,
    course_id: str = Form("default"),
    db: Session = Depends(get_db),
):
    """
    Ingest a previously extracted file into the pgvector knowledge base.
    Reads backend/extracted/{file_id}.json and upserts chunks.
    """
    try:
        result = ingest_file_knowledge(db, file_id, course_id)
        return {"success": True, **result}
    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Ingestion failed: {str(exc)}"},
        )


@app.get("/api/search", tags=["Knowledge Base"])
async def search_knowledge(
    course_id: str,
    query: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
):
    """Semantic vector search over course knowledge chunks."""
    if not query.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "Query must not be empty."},
        )
    results = semantic_search(db, course_id, query, top_k=top_k)
    return {"success": True, "count": len(results), "results": results}


@app.get("/api/knowledge/graph/{course_id}", tags=["Knowledge Base"])
async def concept_graph(course_id: str, db: Session = Depends(get_db)):
    """Retrieve concept relationship graph for a course."""
    graph = get_concept_graph(db, course_id)
    return {"success": True, **graph}


@app.get("/api/knowledge/concept/{concept_id}", tags=["Knowledge Base"])
async def concept_detail(concept_id: str, db: Session = Depends(get_db)):
    """Retrieve detailed information about a specific concept."""
    detail = get_concept_details(db, concept_id)
    if not detail:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Concept '{concept_id}' not found."},
        )
    return {"success": True, **detail}


# ===========================================================================
# Step 7 — Adaptive Quiz Engine
# ===========================================================================

class QuizGenerateRequest(BaseModel):
    course_id: str
    topic_query: str = "General"
    question_types: Optional[List[str]] = None   # ["mcq", "short_answer", "numerical"]
    count: int = 5
    difficulty: str = "medium"
    mode: str = "practice"
    student_id: Optional[str] = None
    title: Optional[str] = None
    adaptive: bool = False



class AnswerSubmitRequest(BaseModel):
    question_id: str
    student_answer: str
    student_id: Optional[str] = None


@app.post("/api/quiz/generate", tags=["Quiz Engine"])
async def quiz_generate(req: QuizGenerateRequest, db: Session = Depends(get_db)):
    """
    Generate a grounded quiz from course material and create a quiz session.

    Workflow:
      1. Retrieve knowledge chunks via semantic_search()
      2. Generate questions heuristically from chunks
      3. Create a QuizSession with the resulting questions
      4. Return quiz_id and question list (NO correct_answer exposed)
    """
    if not req.course_id.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "course_id is required."},
        )
    if not req.topic_query.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "topic_query is required."},
        )
    valid_types = {"mcq", "short_answer", "numerical"}
    if req.question_types and not set(req.question_types).issubset(valid_types):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": f"question_types must be subset of {valid_types}"},
        )

    try:
        if req.adaptive:
            quiz = _create_adaptive_quiz(
                db=db,
                student_id=req.student_id or "student_demo",
                course_id=req.course_id,
                count=req.count,
                question_types=req.question_types,
            )
            return {"success": True, **quiz}

        questions = generate_questions(

            db=db,
            course_id=req.course_id,
            topic_query=req.topic_query,
            question_types=req.question_types,
            count=req.count,
            difficulty=req.difficulty,
        )

        if not questions:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "success": False,
                    "error": (
                        "No questions could be generated. "
                        "Ensure course materials have been uploaded and ingested into the knowledge base."
                    ),
                },
            )

        question_ids = [q["id"] for q in questions]
        quiz = create_quiz(
            db=db,
            course_id=req.course_id,
            question_ids=question_ids,
            title=req.title,
            mode=req.mode,
            student_id=req.student_id,
        )

        return {"success": True, **quiz}

    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Quiz generation failed: {str(exc)}"},
        )


@app.get("/api/quiz/{quiz_id}", tags=["Quiz Engine"])
async def quiz_get(quiz_id: str, db: Session = Depends(get_db)):
    """
    Retrieve quiz session with questions — correct_answer / solution NOT included.
    Safe to return directly to the student UI.
    """
    quiz = get_quiz(db, quiz_id)
    if not quiz:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Quiz '{quiz_id}' not found."},
        )
    return {"success": True, **quiz}


@app.post("/api/quiz/{quiz_id}/answer", tags=["Quiz Engine"])
async def quiz_answer(quiz_id: str, req: AnswerSubmitRequest, db: Session = Depends(get_db)):
    """
    Submit a student's answer for one question. Returns immediate feedback with
    correct_answer and explanation after evaluation.
    """
    result = submit_answer(
        db=db,
        quiz_id=quiz_id,
        question_id=req.question_id,
        student_answer=req.student_answer,
        student_id=req.student_id,
    )
    if "error" in result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": result["error"]},
        )
    return {"success": True, **result}


@app.get("/api/quiz/{quiz_id}/result", tags=["Quiz Engine"])
async def quiz_result(quiz_id: str, db: Session = Depends(get_db)):
    """
    Return full quiz results including per-question breakdowns with correct answers,
    explanations, citations, and overall score/grade.
    """
    result = get_quiz_result(db, quiz_id)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Quiz '{quiz_id}' not found."},
        )
    return {"success": True, **result}


# ===========================================================================
# Step 8 — Learner Model & BKT Progress APIs
# ===========================================================================

from services.mastery_service import (
    get_all_mastery as _get_all_mastery,
    get_weak_topics as _get_weak_topics,
    get_strong_topics as _get_strong_topics,
    get_concept_mastery_list as _get_concept_mastery_list,
    reset_learner_state as _reset_learner_state,
    has_learner_history as _has_learner_history,
)
from services.question_generation_service import generate_questions as _gen_questions
from services.quiz_service import create_quiz as _create_quiz


@app.get("/api/learner/{student_id}/course/{course_id}/mastery", tags=["Learner Model"])
async def learner_mastery(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """
    Return topic-level BKT mastery for a student in a course.
    Overall mastery = mean of topic mastery probabilities (never faked as 0% when no data).
    """
    data = _get_all_mastery(db, student_id, course_id)
    return {"success": True, **data}


@app.get("/api/learner/{student_id}/course/{course_id}/concepts", tags=["Learner Model"])
async def learner_concepts(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """Return concept-level BKT mastery for a student in a course."""
    concepts = _get_concept_mastery_list(db, student_id, course_id)
    return {"success": True, "student_id": student_id, "course_id": course_id, "concepts": concepts}


@app.get("/api/learner/{student_id}/course/{course_id}/weak-topics", tags=["Learner Model"])
async def learner_weak_topics(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """Return topics below the configured WEAK_TOPIC_THRESHOLD."""
    weak = _get_weak_topics(db, student_id, course_id)
    return {"success": True, "student_id": student_id, "course_id": course_id, "weak_topics": weak}


@app.get("/api/learner/{student_id}/course/{course_id}/strong-topics", tags=["Learner Model"])
async def learner_strong_topics(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """Return topics at or above the configured MASTERY_THRESHOLD."""
    strong = _get_strong_topics(db, student_id, course_id)
    return {"success": True, "student_id": student_id, "course_id": course_id, "strong_topics": strong}


@app.post("/api/learner/{student_id}/course/{course_id}/diagnostic", tags=["Learner Model"])
async def learner_diagnostic(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """
    Create a diagnostic quiz if the student has no learner history for this course.
    If history already exists, returns a message without creating a new quiz.
    Reuses the existing quiz engine (Step 7) — no separate diagnostic engine.
    """
    # Check whether history already exists
    if _has_learner_history(db, student_id, course_id):
        return {
            "success": True,
            "diagnostic": False,
            "message": "Diagnostic already completed. Learner history exists for this course.",
        }

    # Generate a representative diagnostic quiz (max 10 questions, mixed types)
    try:
        questions = _gen_questions(
            db=db,
            course_id=course_id,
            topic_query=course_id,   # broad query to cover available material
            question_types=["mcq", "short_answer"],
            count=10,
            difficulty="medium",
        )

        if not questions:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "success": False,
                    "error": (
                        "No questions available for diagnostic. "
                        "Upload and ingest course materials first."
                    ),
                },
            )

        question_ids = [q["id"] for q in questions]
        quiz = _create_quiz(
            db=db,
            course_id=course_id,
            question_ids=question_ids,
            title="Diagnostic Assessment",
            mode="practice",
            student_id=student_id,
        )

        return {
            "success":         True,
            "diagnostic":      True,
            "quiz_id":         quiz["quiz_id"],
            "question_count":  len(question_ids),
            "message":         "Diagnostic quiz created. Complete it to initialize your learner profile.",
        }

    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Diagnostic creation failed: {str(exc)}"},
        )


@app.delete("/api/learner/{student_id}/course/{course_id}/reset", tags=["Learner Model"])
async def learner_reset(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """
    Reset learner mastery state for a student in a course.
    Only deletes LearnerTopicMastery and LearnerConceptMastery rows.
    Does NOT delete uploaded materials, questions, or quiz sessions.
    """
    result = _reset_learner_state(db, student_id, course_id)
    return {"success": True, **result}


# ===========================================================================
# Step 9 — Adaptive Question Selection & Personalized Practice APIs
# ===========================================================================

from services.adaptive_service import (
    get_next_question as _get_next_question,
    create_adaptive_quiz as _create_adaptive_quiz,
    get_adaptive_next_question_for_session as _get_adaptive_next_question_for_session,
)
from services.personalization_service import (
    get_personalized_recommendations as _get_personalized_recommendations,
)


class AdaptiveQuizCreateRequest(BaseModel):
    student_id: str = "student_demo"
    course_id: str
    count: int = 10
    question_types: Optional[List[str]] = None
    topic_id: Optional[str] = None
    concept_id: Optional[str] = None


@app.post("/api/adaptive/quiz", tags=["Adaptive Engine"])
async def adaptive_quiz_create(req: AdaptiveQuizCreateRequest, db: Session = Depends(get_db)):
    """
    Create an adaptive practice quiz session (Step 9).
    Questions are selected dynamically based on current BKT learner state.
    """
    if not req.course_id.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "course_id is required."},
        )

    try:
        res = _create_adaptive_quiz(
            db=db,
            student_id=req.student_id,
            course_id=req.course_id,
            count=req.count,
            question_types=req.question_types,
            topic_id=req.topic_id,
            concept_id=req.concept_id,
        )
        return {"success": True, **res}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Adaptive quiz creation failed: {str(exc)}"},
        )


@app.get("/api/adaptive/next-question", tags=["Adaptive Engine"])
async def adaptive_next_question(
    student_id: str,
    course_id: str,
    quiz_id: Optional[str] = None,
    preferred_type: Optional[str] = None,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Select the optimal next question based on current learner state (Step 9).
    Powers real-time adaptation after each answer submission.
    """
    try:
        if quiz_id:
            res = _get_adaptive_next_question_for_session(
                db=db,
                quiz_id=quiz_id,
                student_id=student_id,
                course_id=course_id,
            )
        else:
            res = _get_next_question(
                db=db,
                student_id=student_id,
                course_id=course_id,
                preferred_question_type=preferred_type,
                target_topic_id=topic_id,
                target_concept_id=concept_id,
            )

        if "error" in res:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND if res.get("status") != "no_questions" else status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"success": False, "error": res["error"]},
            )

        return {"success": True, **res}

    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Failed to select next question: {str(exc)}"},
        )


@app.get("/api/personalization/{student_id}/course/{course_id}", tags=["Personalization"])
async def personalization_recommendations(
    student_id: str,
    course_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve high-level personalized recommendations and study plans (Step 9).
    """
    try:
        res = _get_personalized_recommendations(db=db, student_id=student_id, course_id=course_id)
        return {"success": True, **res}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Failed to generate recommendations: {str(exc)}"},
        )


# ===========================================================================
# Step 10 — Misconception Detection & Personalized Remediation APIs
# ===========================================================================

from services.misconception_service import (
    detect_misconceptions as _detect_misconceptions,
    get_student_misconceptions as _get_student_misconceptions,
    get_misconception_by_id as _get_misconception_by_id,
)
from services.remediation_service import (
    create_remediation as _create_remediation,
)
from services.remediation_tracking_service import (
    get_remediation_session as _get_remediation_session,
    get_student_remediations as _get_student_remediations,
    complete_remediation_activity as _complete_remediation_activity,
    evaluate_remediation_outcome as _evaluate_remediation_outcome,
)


class MisconceptionAnalyzeRequest(BaseModel):
    student_id: str = "student_demo"
    course_id: str
    attempt_id: str


class RemediationCreateRequest(BaseModel):
    student_id: str = "student_demo"
    course_id: str
    topic_id: Optional[str] = None
    concept_id: Optional[str] = None
    misconception_id: Optional[str] = None
    preferred_language: str = "English"


class RemediationCompleteRequest(BaseModel):
    student_id: str = "student_demo"
    activity_id: Optional[str] = None


@app.get("/api/learner/{student_id}/course/{course_id}/misconceptions", tags=["Misconceptions"])
async def learner_misconceptions(
    student_id: str,
    course_id: str,
    status_filter: Optional[str] = None,
    topic_id: Optional[str] = None,
    concept_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Retrieve stored misconceptions for a student in a course (Step 10)."""
    items = _get_student_misconceptions(
        db=db,
        student_id=student_id,
        course_id=course_id,
        status=status_filter,
        topic_id=topic_id,
        concept_id=concept_id,
    )
    return {"success": True, "student_id": student_id, "course_id": course_id, "misconceptions": items}


@app.get("/api/misconceptions/{misconception_id}", tags=["Misconceptions"])
async def misconception_detail(misconception_id: str, db: Session = Depends(get_db)):
    """Retrieve detailed information about a specific misconception."""
    item = _get_misconception_by_id(db, misconception_id)
    if not item:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Misconception '{misconception_id}' not found."},
        )
    return {"success": True, **item}


@app.post("/api/misconceptions/analyze", tags=["Misconceptions"])
async def misconceptions_analyze(req: MisconceptionAnalyzeRequest, db: Session = Depends(get_db)):
    """Trigger diagnostic misconception analysis on a quiz attempt (Step 10)."""
    try:
        res = _detect_misconceptions(
            db=db,
            student_id=req.student_id,
            course_id=req.course_id,
            attempt_id=req.attempt_id,
        )
        if "error" in res:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": res["error"]},
            )
        return {"success": True, **res}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Misconception analysis failed: {str(exc)}"},
        )


@app.post("/api/remediation", tags=["Remediation"])
async def remediation_create(req: RemediationCreateRequest, db: Session = Depends(get_db)):
    """Create a personalized remediation session with grounded explanations and worked examples (Step 10)."""
    try:
        res = _create_remediation(
            db=db,
            student_id=req.student_id,
            course_id=req.course_id,
            topic_id=req.topic_id,
            concept_id=req.concept_id,
            misconception_id=req.misconception_id,
            preferred_language=req.preferred_language,
        )
        return {"success": True, **res}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Remediation creation failed: {str(exc)}"},
        )


@app.get("/api/learner/{student_id}/course/{course_id}/remediation", tags=["Remediation"])
async def learner_remediations(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """List remediation sessions for a student in a course."""
    sessions = _get_student_remediations(db, student_id, course_id)
    return {"success": True, "student_id": student_id, "course_id": course_id, "remediations": sessions}


@app.get("/api/remediation/{session_id}", tags=["Remediation"])
async def remediation_detail(session_id: str, db: Session = Depends(get_db)):
    """Retrieve full detail of a single remediation session."""
    session = _get_remediation_session(db, session_id)
    if not session:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Remediation session '{session_id}' not found."},
        )
    return {"success": True, **session}


@app.post("/api/remediation/{session_id}/complete", tags=["Remediation"])
async def remediation_complete(session_id: str, req: RemediationCompleteRequest, db: Session = Depends(get_db)):
    """Complete a remediation activity or full session."""
    res = _complete_remediation_activity(
        db=db,
        session_id=session_id,
        activity_id=req.activity_id,
        student_id=req.student_id,
    )
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


@app.get("/api/remediation/{session_id}/outcome", tags=["Remediation"])
async def remediation_outcome(session_id: str, student_id: str, course_id: str, db: Session = Depends(get_db)):
    """Evaluate post-remediation evidence cautious outcome (Step 10)."""
    res = _evaluate_remediation_outcome(
        db=db,
        student_id=student_id,
        course_id=course_id,
        session_id=session_id,
    )
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


# ===========================================================================
# Step 11 — Personalized Revision Materials & Flashcard Engine
# ===========================================================================

class RevisionGenerateRequest(BaseModel):
    student_id: str = "student_demo"
    course_id: str
    topic_id: Optional[str] = None
    material_type: str = "revision_notes"
    language: str = "English"
    depth: str = "standard"


class FlashcardGenerateRequest(BaseModel):
    student_id: str = "student_demo"
    course_id: str
    topic_id: Optional[str] = None
    card_count: int = 10
    language: str = "English"
    difficulty_mix: str = "balanced"


class FlashcardReviewRequest(BaseModel):
    student_id: str = "student_demo"
    rating: str  # again | hard | good | easy
    duration_ms: Optional[int] = None


@app.post("/api/revision/generate", tags=["Revision Studio"])
async def revision_generate(req: RevisionGenerateRequest, db: Session = Depends(get_db)):
    """Generate a personalized, grounded revision resource (Step 11)."""
    try:
        res = generate_revision_material(
            db=db,
            student_id=req.student_id,
            course_id=req.course_id,
            topic_id=req.topic_id,
            material_type=req.material_type,
            language=req.language,
            depth=req.depth,
        )
        if "error" in res and res.get("insufficient_materials"):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": res["error"]},
            )
        elif "error" in res:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": res["error"]},
            )
        return {"success": True, **res}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Revision generation failed: {str(exc)}"},
        )


@app.get("/api/learner/{student_id}/course/{course_id}/revision", tags=["Revision Studio"])
async def learner_revision_materials(
    student_id: str,
    course_id: str,
    material_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List saved revision resources for a student in a course."""
    mats = get_student_revision_materials(db, student_id, course_id, material_type=material_type)
    return {"success": True, "student_id": student_id, "course_id": course_id, "materials": mats}


@app.get("/api/revision/{material_id}", tags=["Revision Studio"])
async def revision_detail(material_id: str, student_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve full detail of a single revision resource."""
    mat = get_revision_material(db, material_id, student_id=student_id)
    if not mat or "error" in mat:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND if not mat else status.HTTP_403_FORBIDDEN,
            content={"success": False, "error": mat.get("error") if mat else f"Revision material '{material_id}' not found."},
        )
    return {"success": True, **mat}


@app.delete("/api/revision/{material_id}", tags=["Revision Studio"])
async def revision_delete(material_id: str, student_id: str = "student_demo", db: Session = Depends(get_db)):
    """Delete a saved revision material."""
    res = delete_revision_material(db, material_id, student_id=student_id)
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


@app.post("/api/flashcards/generate", tags=["Flashcards"])
async def flashcards_generate(req: FlashcardGenerateRequest, db: Session = Depends(get_db)):
    """Generate a grounded flashcard deck (Step 11)."""
    try:
        deck = generate_flashcard_deck(
            db=db,
            student_id=req.student_id,
            course_id=req.course_id,
            topic_id=req.topic_id,
            card_count=req.card_count,
            language=req.language,
            difficulty_mix=req.difficulty_mix,
        )
        if not deck:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": "Failed to generate flashcard deck."},
            )
        return {"success": True, **deck}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Flashcard generation failed: {str(exc)}"},
        )


@app.get("/api/learner/{student_id}/course/{course_id}/flashcards", tags=["Flashcards"])
async def learner_flashcard_decks(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """List flashcard decks for a student in a course."""
    decks = get_student_flashcard_decks(db, student_id, course_id)
    return {"success": True, "student_id": student_id, "course_id": course_id, "decks": decks}


@app.get("/api/flashcards/deck/{deck_id}", tags=["Flashcards"])
async def flashcard_deck_detail(deck_id: str, db: Session = Depends(get_db)):
    """Retrieve full detail of a flashcard deck."""
    deck = get_flashcard_deck(db, deck_id)
    if not deck:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Flashcard deck '{deck_id}' not found."},
        )
    return {"success": True, **deck}


@app.post("/api/flashcards/{card_id}/review", tags=["Flashcards"])
async def flashcard_review(card_id: str, req: FlashcardReviewRequest, db: Session = Depends(get_db)):
    """Record a student's recall rating (again, hard, good, easy) for a card."""
    res = record_card_review(
        db=db,
        card_id=card_id,
        student_id=req.student_id,
        rating=req.rating,
        duration_ms=req.duration_ms,
    )
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


@app.get("/api/flashcards/deck/{deck_id}/reviews", tags=["Flashcards"])
async def flashcard_deck_reviews(deck_id: str, student_id: str = "student_demo", db: Session = Depends(get_db)):
    """Retrieve review history for a flashcard deck."""
    reviews = get_deck_reviews(db, deck_id, student_id=student_id)
    return {"success": True, "deck_id": deck_id, "student_id": student_id, "reviews": reviews}


@app.delete("/api/flashcards/deck/{deck_id}", tags=["Flashcards"])
async def flashcard_deck_delete(deck_id: str, student_id: str = "student_demo", db: Session = Depends(get_db)):
    """Delete a flashcard deck."""
    res = delete_flashcard_deck(db, deck_id, student_id=student_id)
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


# ===========================================================================
# Step 12 — Intelligent Study Planner & Spaced Repetition Endpoints
# ===========================================================================

class GenerateStudyPlanRequest(BaseModel):
    student_id: str = "demo_student"
    course_id: str
    horizon_days: int = 7
    daily_minutes_budget: Optional[int] = None
    exam_date: Optional[str] = None
    selected_topics: Optional[List[str]] = None
    unavailable_dates: Optional[List[str]] = None


class UpdateTaskStatusRequest(BaseModel):
    student_id: str = "demo_student"
    status: str
    scheduled_start: Optional[str] = None
    target_date_str: Optional[str] = None


class CompleteTaskRequest(BaseModel):
    student_id: str = "demo_student"
    actual_minutes: Optional[int] = None
    completion_metadata: Optional[dict] = None


class UpdateStudyPreferencesRequest(BaseModel):
    daily_minutes_budget: Optional[int] = None
    exam_date: Optional[str] = None
    preferred_session_minutes: Optional[int] = None
    selected_topics: Optional[List[str]] = None
    unavailable_dates: Optional[List[str]] = None


@app.post("/api/study-plan/generate", tags=["Study Planner"])
async def study_plan_generate(req: GenerateStudyPlanRequest, db: Session = Depends(get_db)):
    """Generate a personalized 7- or 14-day study plan (Step 12)."""
    try:
        ex_dt = None
        if req.exam_date:
            try:
                ex_dt = datetime.fromisoformat(req.exam_date.replace("Z", "+00:00"))
            except Exception:
                ex_dt = None

        plan = generate_study_plan(
            db=db,
            student_id=req.student_id,
            course_id=req.course_id,
            horizon_days=req.horizon_days,
            daily_minutes_budget=req.daily_minutes_budget,
            exam_date=ex_dt,
            selected_topics=req.selected_topics,
            unavailable_dates=req.unavailable_dates,
        )
        if isinstance(plan, dict) and "error" in plan:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": plan["error"]},
            )
        return {"success": True, **plan}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Study plan generation failed: {str(exc)}"},
        )


@app.get("/api/learner/{student_id}/course/{course_id}/study-plan", tags=["Study Planner"])
async def active_study_plan(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """Retrieve the current active study plan for a student and course."""
    plan = get_active_study_plan(db, student_id, course_id)
    if not plan:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": "No active study plan found. Generate one first."},
        )
    return {"success": True, **plan}


@app.get("/api/study-plan/{plan_id}", tags=["Study Planner"])
async def study_plan_by_id(plan_id: str, db: Session = Depends(get_db)):
    """Retrieve details of a specific study plan by ID."""
    from database.models import StudyPlan
    p = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    if not p:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Study plan '{plan_id}' not found."},
        )
    plan = get_active_study_plan(db, p.student_id, p.course_id)
    return {"success": True, **(plan or {})}


@app.get("/api/learner/{student_id}/course/{course_id}/study-plan/today", tags=["Study Planner"])
async def today_study_tasks(student_id: str, course_id: str, date: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve today's tasks and planned minutes for the student dashboard."""
    tasks_data = get_today_tasks(db, student_id, course_id, date_str=date)
    return {"success": True, **tasks_data}


@app.patch("/api/study-plan/tasks/{task_id}", tags=["Study Planner"])
async def study_plan_task_update(task_id: str, req: UpdateTaskStatusRequest, db: Session = Depends(get_db)):
    """Update task status (pending, in_progress, completed, skipped, rescheduled, cancelled)."""
    sched_dt = None
    if req.scheduled_start:
        try:
            sched_dt = datetime.fromisoformat(req.scheduled_start.replace("Z", "+00:00"))
        except Exception:
            sched_dt = None

    res = update_task_status(
        db=db,
        task_id=task_id,
        student_id=req.student_id,
        status=req.status,
        scheduled_start=sched_dt,
        target_date_str=req.target_date_str,
    )
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


@app.post("/api/study-plan/tasks/{task_id}/complete", tags=["Study Planner"])
async def study_plan_task_complete(task_id: str, req: CompleteTaskRequest, db: Session = Depends(get_db)):
    """Record task completion with actual study minutes and optional completion feedback."""
    res = complete_task(
        db=db,
        task_id=task_id,
        student_id=req.student_id,
        actual_minutes=req.actual_minutes,
        completion_metadata=req.completion_metadata,
    )
    if "error" in res:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": res["error"]},
        )
    return {"success": True, **res}


@app.get("/api/learner/{student_id}/course/{course_id}/reviews/due", tags=["Spaced Repetition"])
async def spaced_repetition_due_queue(student_id: str, course_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """Retrieve due flashcards for spaced repetition study."""
    due_cards = get_due_flashcards(db, student_id, course_id, limit=limit)
    return {
        "success": True,
        "student_id": student_id,
        "course_id": course_id,
        "due_count": len(due_cards),
        "due_cards": due_cards,
    }


@app.get("/api/learner/{student_id}/course/{course_id}/exam-readiness", tags=["Exam Readiness"])
async def learner_exam_readiness(student_id: str, course_id: str, db: Session = Depends(get_db)):
    """Evaluate student exam readiness based on empirical learner evidence."""
    readiness = evaluate_exam_readiness(db, student_id, course_id)
    return {"success": True, **readiness}


@app.patch("/api/learner/{student_id}/course/{course_id}/study-preferences", tags=["Study Planner"])
async def update_study_preferences(student_id: str, course_id: str, req: UpdateStudyPreferencesRequest, db: Session = Depends(get_db)):
    """Update student study preferences (daily budget, exam date, selected topics, etc.)."""
    ex_dt = None
    if req.exam_date:
        try:
            ex_dt = datetime.fromisoformat(req.exam_date.replace("Z", "+00:00"))
        except Exception:
            ex_dt = None

    prefs = get_or_create_preferences(
        db=db,
        student_id=student_id,
        course_id=course_id,
        daily_minutes_budget=req.daily_minutes_budget,
        exam_date=ex_dt,
        preferred_session_minutes=req.preferred_session_minutes,
        selected_topics=req.selected_topics,
        unavailable_dates=req.unavailable_dates,
    )

    return {
        "success": True,
        "student_id": student_id,
        "course_id": course_id,
        "daily_minutes_budget": prefs.daily_minutes_budget,
        "exam_date": prefs.exam_date.isoformat() if prefs.exam_date else None,
        "preferred_session_minutes": prefs.preferred_session_minutes,
        "selected_topics": prefs.selected_topics or [],
        "unavailable_dates": prefs.unavailable_dates or [],
    }


# ===========================================================================
# Step 13 — Evaluation & Benchmarking Framework Endpoints
# ===========================================================================

class RunEvaluationRequest(BaseModel):
    task_type: Optional[str] = None
    dataset_version: str = "1.0"
    deterministic_only: bool = True
    max_cases: Optional[int] = None


@app.post("/api/evaluation/runs", tags=["Evaluation & Benchmarks"])
async def trigger_evaluation_run(req: RunEvaluationRequest, db: Session = Depends(get_db)):
    """Trigger a reproducible system evaluation benchmark run (Step 13)."""
    try:
        from evaluation.evaluation_runner import run_evaluation
        summary = run_evaluation(
            db=db,
            task_type=req.task_type,
            dataset_version=req.dataset_version,
            deterministic_only=req.deterministic_only,
            max_cases=req.max_cases,
        )
        return {"success": True, **summary.model_dump()}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Evaluation run failed: {str(exc)}"},
        )


@app.get("/api/evaluation/runs", tags=["Evaluation & Benchmarks"])
async def list_evaluation_runs():
    """List historical evaluation runs stored in evaluation_results/."""
    import json
    from evaluation.config import RESULTS_DIR
    runs = []
    if os.path.exists(RESULTS_DIR):
        for entry in os.listdir(RESULTS_DIR):
            run_dir = os.path.join(RESULTS_DIR, entry)
            if os.path.isdir(run_dir):
                meta_file = os.path.join(run_dir, "run_metadata.json")
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            runs.append(json.load(f))
                    except Exception:
                        pass
    runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"success": True, "count": len(runs), "runs": runs}


@app.get("/api/evaluation/runs/{run_id}", tags=["Evaluation & Benchmarks"])
async def get_evaluation_run(run_id: str):
    """Retrieve details of a specific evaluation run."""
    import json
    from evaluation.config import RESULTS_DIR
    run_dir = os.path.join(RESULTS_DIR, f"run_{run_id}")
    if not os.path.exists(run_dir):
        # Fallback to direct folder matching
        run_dir = os.path.join(RESULTS_DIR, run_id)
        if not os.path.exists(run_dir):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "error": f"Evaluation run '{run_id}' not found."},
            )

    meta_file = os.path.join(run_dir, "run_metadata.json")
    if not os.path.exists(meta_file):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Run metadata missing for '{run_id}'."},
        )

    with open(meta_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"success": True, **data}


@app.get("/api/evaluation/runs/{run_id}/metrics", tags=["Evaluation & Benchmarks"])
async def get_evaluation_run_metrics(run_id: str):
    """Retrieve aggregated metrics summary for an evaluation run."""
    import json
    from evaluation.config import RESULTS_DIR
    run_dir = os.path.join(RESULTS_DIR, f"run_{run_id}")
    if not os.path.exists(run_dir):
        run_dir = os.path.join(RESULTS_DIR, run_id)

    metrics_file = os.path.join(run_dir, "metrics_summary.json")
    if not os.path.exists(metrics_file):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Metrics summary missing for '{run_id}'."},
        )

    with open(metrics_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"success": True, "run_id": run_id, "metrics": data}


@app.get("/api/evaluation/runs/{run_id}/cases", tags=["Evaluation & Benchmarks"])
async def get_evaluation_run_cases(run_id: str):
    """Retrieve case-by-case evaluation results for an evaluation run."""
    import json
    from evaluation.config import RESULTS_DIR
    run_dir = os.path.join(RESULTS_DIR, f"run_{run_id}")
    if not os.path.exists(run_dir):
        run_dir = os.path.join(RESULTS_DIR, run_id)

    cases_file = os.path.join(run_dir, "case_results.jsonl")
    if not os.path.exists(cases_file):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Case results file missing for '{run_id}'."},
        )

    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                cases.append(json.loads(line_str))

    return {"success": True, "run_id": run_id, "count": len(cases), "cases": cases}


# ===========================================================================
# Step 14 — Multimodal Course Understanding & Visual Intelligence Endpoints
# ===========================================================================

class VisualProcessRequest(BaseModel):
    skip_vision: Optional[bool] = False


@app.post("/api/visuals/process/{material_id}", tags=["Visual Intelligence"])
async def trigger_visual_processing(
    material_id: str,
    req: VisualProcessRequest = None,
    db: Session = Depends(get_db),
):
    """
    Trigger visual extraction, optional vision analysis, and semantic indexing
    for a specific course material.
    """
    skip_vision = req.skip_vision if req else False
    result = process_material_visuals(db, material_id=material_id, skip_vision=skip_vision)
    if not result.get("success", False):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result,
        )
    return result


@app.get("/api/visuals/status/{material_id}", tags=["Visual Intelligence"])
async def get_visual_processing_status(
    material_id: str,
    db: Session = Depends(get_db),
):
    """
    Check visual processing status, asset counts, and errors for a specific material.
    """
    status_info = get_material_visual_status(db, material_id=material_id)
    return {"success": True, **status_info}


@app.get("/api/courses/{course_id}/visuals", tags=["Visual Intelligence"])
async def list_course_visuals(
    course_id: str,
    source_type: Optional[str] = None,
    asset_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """
    List extracted visual assets for a course with pagination and type filters.
    Strictly course-isolated.
    """
    data = list_course_visual_assets(
        db,
        course_id=course_id,
        source_type=source_type,
        asset_type=asset_type,
        page=page,
        page_size=page_size,
    )
    return {"success": True, **data}


@app.get("/api/courses/{course_id}/visuals/{asset_id}", tags=["Visual Intelligence"])
async def get_course_visual_detail(
    course_id: str,
    asset_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve full details including structured visual description for a specific visual asset.
    Strictly verifies course ownership.
    """
    asset = get_visual_asset_detail(db, asset_id=asset_id, course_id=course_id)
    if not asset:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Visual asset '{asset_id}' not found in course '{course_id}'."},
        )
    return {"success": True, "asset": asset}


@app.get("/api/visuals/assets/{asset_id}/image", tags=["Visual Intelligence"])
async def get_visual_asset_image(
    asset_id: str,
    db: Session = Depends(get_db),
):
    """
    Authorized endpoint to serve image bytes for a visual asset safely without
    exposing backend filesystem directory paths.
    """
    from database.models import VisualAsset
    from fastapi.responses import FileResponse

    va = db.get(VisualAsset, asset_id)
    if not va or not va.image_path:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": f"Image for asset '{asset_id}' not found."},
        )

    image_path = os.path.abspath(va.image_path)
    if not os.path.exists(image_path):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": "Image file missing from storage."},
        )

    return FileResponse(image_path, media_type="image/jpeg")


@app.get("/api/courses/{course_id}/visuals/search", tags=["Visual Intelligence"])
async def search_course_visuals(
    course_id: str,
    query: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
):
    """
    Search indexed visual content using semantic similarity with strict course isolation.
    """
    results = search_visual_descriptions(db, course_id=course_id, query=query, top_k=top_k)
    return {
        "success": True,
        "course_id": course_id,
        "query": query,
        "count": len(results),
        "results": results,
    }


@app.get("/api/visuals/provider-info", tags=["Visual Intelligence"])
async def get_vision_provider_info():
    """
    Return status of vision model configuration (whether API key is configured).
    Does NOT leak API key.
    """
    return {
        "success": True,
        "vision_available": vision_available(),
        "vision_model": os.getenv("VISION_MODEL", "gemini-1.5-flash"),
    }


# ===========================================================================
# Step 15 — Grounded AI Tutor & System Dashboard Aggregation
# ===========================================================================

class TutorAskRequest(BaseModel):
    course_id: str
    question: str
    student_id: Optional[str] = None
    preferred_language: Optional[str] = "English"


@app.post("/api/tutor/ask", tags=["AI Tutor"])
async def ask_ai_tutor(req: TutorAskRequest, db: Session = Depends(get_db)):
    """
    Ask a grounded educational question to the AI Tutor.
    Answers strictly using retrieved course chunks with citations.
    Safely abstains when relevant evidence is insufficient.
    """
    if not req.question or not req.question.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "Question must not be empty."},
        )

    result = answer_student_question(
        db=db,
        course_id=req.course_id,
        question=req.question,
        preferred_language=req.preferred_language or "English",
    )
    return {"success": True, **result}


@app.get("/api/dashboard/summary", tags=["Dashboard"])
async def get_dashboard_summary(
    student_id: str = "student_demo",
    course_id: str = "general",
    db: Session = Depends(get_db),
):
    """
    Unified summary endpoint for student dashboard.
    Aggregates material counts, indexed chunks, topics, misconceptions, and study tasks.
    """
    from database.models import (
        Material,
        KnowledgeChunk,
        Topic,
        MisconceptionRecord,
        VisualAsset,
    )
    from services.mastery_service import get_all_mastery
    from services.exam_readiness_service import evaluate_exam_readiness
    from services.study_planner_service import get_today_tasks

    # Materials
    materials_count = db.query(Material).filter(Material.course_id == course_id).count()
    chunks_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.course_id == course_id).count()
    topics_count = db.query(Topic).filter(Topic.course_id == course_id).count()
    visuals_count = db.query(VisualAsset).filter(VisualAsset.course_id == course_id).count()

    # Active Misconceptions
    active_misconceptions = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == student_id,
        MisconceptionRecord.course_id == course_id,
        MisconceptionRecord.status.in_(["suspected", "supported", "under_review"]),
    ).count()

    # Learner Mastery
    mastery_info = get_all_mastery(db, student_id=student_id, course_id=course_id)

    # Exam Readiness
    readiness = evaluate_exam_readiness(db, student_id=student_id, course_id=course_id)

    # Today's Study Tasks
    today_tasks_res = get_today_tasks(db, student_id=student_id, course_id=course_id)
    today_tasks_count = len(today_tasks_res.get("tasks", [])) if today_tasks_res.get("has_plan") else 0

    return {
        "success": True,
        "student_id": student_id,
        "course_id": course_id,
        "materials_count": materials_count,
        "chunks_count": chunks_count,
        "topics_count": topics_count,
        "visuals_count": visuals_count,
        "active_misconceptions_count": active_misconceptions,
        "overall_mastery": mastery_info.get("overall_mastery"),
        "has_mastery_history": mastery_info.get("has_history", False),
        "exam_readiness": readiness.get("category_label", "Insufficient Data"),
        "exam_readiness_score": readiness.get("readiness_score", 0.0),
        "today_tasks_count": today_tasks_count,
    }


# ===========================================================================
# Step 15 — Demo Mode Endpoints
# ===========================================================================

@app.post("/api/demo/enable", tags=["Demo Mode"])
async def enable_demo_mode(db: Session = Depends(get_db)):
    """Initialize deterministic demo fixtures for live presentations."""
    from services.demo_service import ensure_demo_fixtures
    res = ensure_demo_fixtures(db)
    return res


@app.post("/api/demo/reset", tags=["Demo Mode"])
async def reset_demo_mode(db: Session = Depends(get_db)):
    """Reset demo student and demo physics course without touching real user records."""
    from services.demo_service import reset_demo_fixtures
    res = reset_demo_fixtures(db)
    return res





