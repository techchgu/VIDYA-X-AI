"""
VIDYA-X AI — Step 7 Quiz Engine Tests
Tests the question service, generation service, verification service, and quiz service.
Runs with SQLite in-memory so no live PostgreSQL is required.
"""

import os
import sys
import uuid

# Use SQLite in-memory for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_quiz.db"

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import engine, SessionLocal
from database.models import Base, KnowledgeChunk, Course


# ---------------------------------------------------------------------------
# Schema setup for SQLite test DB
# ---------------------------------------------------------------------------

def setup_db():
    """Create all tables (including Step 7 quiz tables) in the test SQLite DB."""
    # pgvector.sqlalchemy.Vector is not available in SQLite — patch it
    import sqlalchemy as sa
    from database import models

    # Override Vector column to TEXT for SQLite tests
    original_vector = None
    try:
        from pgvector.sqlalchemy import Vector
        original_vector = Vector
    except ImportError:
        pass

    if original_vector:
        # Monkey-patch: replace Vector columns with Text in SQLite context
        for model_class in [models.KnowledgeChunk]:
            for col in model_class.__table__.columns:
                if hasattr(col.type, '__class__') and col.type.__class__.__name__ == 'Vector':
                    col.type = sa.Text()

    Base.metadata.create_all(bind=engine)


def teardown_db():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    import os
    try:
        if os.path.exists("test_quiz.db"):
            os.remove("test_quiz.db")
    except PermissionError:
        pass  # Windows may still hold the file; safe to ignore during test cleanup


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

PASS = "[OK]"
FAIL = "[FAIL]"
_results = []


def run_test(name, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        _results.append((name, True, None))
    except Exception as exc:
        print(f"  {FAIL}  {name}: {exc}")
        _results.append((name, False, str(exc)))


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def seed_course_and_chunks(db):
    """Insert a dummy course + knowledge chunks for grounding tests."""
    course_id = "test-course-" + str(uuid.uuid4())[:8]
    course = Course(id=course_id, name="Test Physics Course")
    db.add(course)

    chunks = [
        ("Newton's first law is an object at rest stays at rest unless acted on by a force", "definition"),
        ("Newton's second law: F = ma where F is force, m is mass, a is acceleration", "definition"),
        ("Velocity is the rate of change of displacement", "definition"),
        ("Momentum refers to the product of mass and velocity", "definition"),
        ("Energy is the capacity to do work and is measured in joules: 1 joule = 1 N times 1 m", "concept"),
        ("The speed of light is approximately 3 times 10^8 meters per second", "concept"),
    ]

    chunk_ids = []
    for text, ctype in chunks:
        cid = str(uuid.uuid4()).replace("-", "")
        chunk = KnowledgeChunk(
            id=cid,
            course_id=course_id,
            content=text,
            chunk_type=ctype,
            embedding=None,
            chunk_metadata={
                "file_name": "physics.pdf",
                "source_type": "pdf",
                "page": 1,
            },
        )
        db.add(chunk)
        chunk_ids.append(cid)

    db.commit()
    return course_id, chunk_ids


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

def run_tests():
    print("\n" + "=" * 60)
    print("  VIDYA-X AI — Step 7 Quiz Engine Tests")
    print("=" * 60)

    setup_db()
    db = SessionLocal()

    course_id, chunk_ids = seed_course_and_chunks(db)

    # ── 1. Fingerprinting ────────────────────────────────────────────────
    print("\n[1] Question Service — Fingerprinting")

    def test_fingerprint_deterministic():
        from services.question_service import compute_fingerprint
        fp1 = compute_fingerprint("What is Newton's first law?")
        fp2 = compute_fingerprint("What is Newton's first law?")
        assert fp1 == fp2, "Same prompt must yield same fingerprint"
        assert len(fp1) == 64, f"Fingerprint must be 64 chars, got {len(fp1)}"

    def test_fingerprint_case_insensitive():
        from services.question_service import compute_fingerprint
        fp1 = compute_fingerprint("What Is VELOCITY?")
        fp2 = compute_fingerprint("what is velocity")
        assert fp1 == fp2, "Fingerprint must be case-insensitive"

    def test_fingerprint_different_prompts():
        from services.question_service import compute_fingerprint
        fp1 = compute_fingerprint("What is force?")
        fp2 = compute_fingerprint("What is momentum?")
        assert fp1 != fp2, "Different prompts must have different fingerprints"

    run_test("compute_fingerprint is deterministic", test_fingerprint_deterministic)
    run_test("compute_fingerprint is case-insensitive", test_fingerprint_case_insensitive)
    run_test("different prompts produce different fingerprints", test_fingerprint_different_prompts)

    # ── 2. Store & Deduplicate ───────────────────────────────────────────
    print("\n[2] Question Service — Store & Deduplication")

    def test_store_question():
        from services.question_service import store_question, get_question_by_id, compute_fingerprint
        q_data = {
            "course_id": course_id,
            "question_type": "short_answer",
            "prompt": "What is velocity?",
            "difficulty": "easy",
            "correct_answer": "the rate of change of displacement",
            "explanation": "From course material",
            "source_refs": [{"chunk_id": chunk_ids[2], "file_name": "physics.pdf", "page": 1}],
        }
        q_id = store_question(db, q_data)
        assert q_id, "store_question must return an ID"
        q = get_question_by_id(db, q_id, include_answer=True)
        assert q is not None, "Should retrieve stored question"
        assert q["correct_answer"] == "the rate of change of displacement"

    def test_deduplication():
        from services.question_service import store_question, question_exists, compute_fingerprint
        prompt = "What is momentum? [dup-test]"
        q_data = {
            "course_id": course_id,
            "question_type": "short_answer",
            "prompt": prompt,
            "difficulty": "medium",
            "correct_answer": "mass times velocity",
            "source_refs": [{"chunk_id": chunk_ids[3]}],
        }
        id1 = store_question(db, q_data)
        id2 = store_question(db, q_data)
        assert id1 == id2, "Storing the same question twice must return the same ID (deduplication)"

    def test_answer_hidden_by_default():
        from services.question_service import store_question, get_question_by_id
        q_data = {
            "course_id": course_id,
            "question_type": "short_answer",
            "prompt": "Define force [hidden-test]",
            "difficulty": "easy",
            "correct_answer": "push or pull",
            "source_refs": [{"chunk_id": chunk_ids[0]}],
        }
        q_id = store_question(db, q_data)
        q = get_question_by_id(db, q_id, include_answer=False)
        assert "correct_answer" not in q, "correct_answer must NOT appear when include_answer=False"

    run_test("store_question persists and is retrievable", test_store_question)
    run_test("duplicate questions are deduplicated", test_deduplication)
    run_test("correct_answer hidden when include_answer=False", test_answer_hidden_by_default)

    # ── 3. Verification Service ──────────────────────────────────────────
    print("\n[3] Verification Service")

    def test_valid_mcq_passes():
        from services.question_verification_service import verify_question
        q = {
            "course_id": course_id,
            "question_type": "mcq",
            "prompt": "Which law states F = ma?",
            "correct_answer": "B",
            "options": [
                {"key": "A", "text": "First law",  "is_correct": False},
                {"key": "B", "text": "Second law", "is_correct": True},
                {"key": "C", "text": "Third law",  "is_correct": False},
                {"key": "D", "text": "None",        "is_correct": False},
            ],
            "source_refs": [{"chunk_id": chunk_ids[1]}],
        }
        passed, errors = verify_question(db, q)
        assert passed, f"Valid MCQ should pass verification. Errors: {errors}"

    def test_mcq_wrong_answer_key_fails():
        from services.question_verification_service import verify_question
        q = {
            "course_id": course_id,
            "question_type": "mcq",
            "prompt": "Test question?",
            "correct_answer": "E",   # invalid — no option E
            "options": [
                {"key": "A", "text": "opt A", "is_correct": False},
                {"key": "B", "text": "opt B", "is_correct": True},
                {"key": "C", "text": "opt C", "is_correct": False},
                {"key": "D", "text": "opt D", "is_correct": False},
            ],
            "source_refs": [{"chunk_id": chunk_ids[0]}],
        }
        passed, errors = verify_question(db, q)
        assert not passed, "MCQ with wrong correct_answer key must fail verification"

    def test_missing_source_ref_fails():
        from services.question_verification_service import verify_question
        q = {
            "course_id": course_id,
            "question_type": "short_answer",
            "prompt": "What is energy?",
            "correct_answer": "capacity to do work",
            "source_refs": [],   # empty — must fail
        }
        passed, errors = verify_question(db, q)
        assert not passed, "Question with no source_refs must fail grounding check"

    run_test("valid MCQ passes verification", test_valid_mcq_passes)
    run_test("MCQ with invalid correct_answer key fails", test_mcq_wrong_answer_key_fails)
    run_test("question without source_refs fails grounding check", test_missing_source_ref_fails)

    # ── 4. Quiz Service ──────────────────────────────────────────────────
    print("\n[4] Quiz Service")

    # Pre-store a question for quiz tests
    from services.question_service import store_question
    quiz_q = store_question(db, {
        "course_id": course_id,
        "question_type": "short_answer",
        "prompt": "What is Newton's first law? [quiz-test]",
        "difficulty": "medium",
        "correct_answer": "an object at rest stays at rest unless acted on by a force",
        "explanation": "Newton's 1st Law of Motion",
        "source_refs": [{"chunk_id": chunk_ids[0], "file_name": "physics.pdf", "page": 1}],
    })

    def test_create_quiz():
        from services.quiz_service import create_quiz
        quiz = create_quiz(db, course_id, [quiz_q], title="Physics Test", mode="practice")
        assert quiz["quiz_id"], "Quiz must have an ID"
        assert quiz["total_questions"] == 1
        # Answers must NOT be in the response
        for q in quiz.get("questions", []):
            assert "correct_answer" not in q, "correct_answer must not appear in GET quiz response"

    def test_get_quiz_no_answers():
        from services.quiz_service import create_quiz, get_quiz
        quiz = create_quiz(db, course_id, [quiz_q], mode="practice")
        fetched = get_quiz(db, quiz["quiz_id"])
        assert fetched is not None
        for q in fetched.get("questions", []):
            assert "correct_answer" not in q, "correct_answer must be absent in get_quiz response"

    def test_submit_answer_correct():
        from services.quiz_service import create_quiz, submit_answer
        quiz = create_quiz(db, course_id, [quiz_q], mode="practice")
        result = submit_answer(
            db, quiz["quiz_id"], quiz_q,
            "an object at rest stays at rest unless acted on by a force"
        )
        assert "is_correct" in result, "Submit must return is_correct"
        assert result["is_correct"] is True
        assert "correct_answer" in result, "Correct answer must be revealed after submission"

    def test_quiz_result_after_attempt():
        from services.quiz_service import create_quiz, submit_answer, get_quiz_result
        quiz = create_quiz(db, course_id, [quiz_q], mode="practice")
        submit_answer(db, quiz["quiz_id"], quiz_q, "rest and force")
        result = get_quiz_result(db, quiz["quiz_id"])
        assert result is not None
        assert "score_percent" in result
        assert "grade" in result
        assert result["total_questions"] == 1

    run_test("create_quiz returns session without answers", test_create_quiz)
    run_test("get_quiz hides correct_answer", test_get_quiz_no_answers)
    run_test("submit_answer evaluates and reveals answer", test_submit_answer_correct)
    run_test("get_quiz_result returns complete breakdown", test_quiz_result_after_attempt)

    # ── Summary ──────────────────────────────────────────────────────────
    db.close()
    teardown_db()

    total  = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  -- ALL TESTS PASSED")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
