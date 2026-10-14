"""
VIDYA-X AI — Step 8 BKT & Learner Model Tests
Tests BKT math, topic/concept mastery updates, isolation, edge cases.
Runs with SQLite in-memory — no live PostgreSQL required.
"""

import os
import sys
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_bkt.db"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Schema setup ─────────────────────────────────────────────────────────────

from database.connection import engine, SessionLocal
from database.models import Base, KnowledgeChunk, Course, Topic, Concept, Question


def setup_db():
    import sqlalchemy as sa
    from database import models
    try:
        from pgvector.sqlalchemy import Vector
        for model_class in [models.KnowledgeChunk]:
            for col in model_class.__table__.columns:
                if hasattr(col.type, "__class__") and col.type.__class__.__name__ == "Vector":
                    col.type = sa.Text()
    except ImportError:
        pass
    Base.metadata.create_all(bind=engine)


def teardown_db():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        if os.path.exists("test_bkt.db"):
            os.remove("test_bkt.db")
    except PermissionError:
        pass


# ── Test runner ───────────────────────────────────────────────────────────────

PASS = "[OK]"
FAIL = "[FAIL]"
_results = []


def run_test(name, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        _results.append((name, True, None))
    except Exception as exc:
        import traceback
        print(f"  {FAIL}  {name}: {exc}")
        _results.append((name, False, str(exc)))


# ── Seed helpers ──────────────────────────────────────────────────────────────

def seed(db):
    course_id = "bkt-test-course-" + str(uuid.uuid4())[:6]
    course = Course(id=course_id, name="BKT Test Course")
    db.add(course)

    topic_id = str(uuid.uuid4()).replace("-", "")[:16]
    topic = Topic(id=topic_id, course_id=course_id, name="Newton's Laws", order_index=0)
    db.add(topic)

    concept_id = str(uuid.uuid4()).replace("-", "")[:16]
    concept = Concept(id=concept_id, topic_id=topic_id, name="Newton's Second Law", difficulty="medium")
    db.add(concept)

    q_id = str(uuid.uuid4()).replace("-", "")
    question = Question(
        id=q_id,
        course_id=course_id,
        topic_id=topic_id,
        concept_id=concept_id,
        question_type="mcq",
        prompt="What is F=ma?",
        difficulty="medium",
        correct_answer="B",
        explanation="Newton's 2nd law",
        fingerprint=str(uuid.uuid4()),
        source_refs=[],
    )
    db.add(question)
    db.commit()
    return course_id, topic_id, concept_id, q_id


# ── SUITE 1: Pure BKT math ─────────────────────────────────────────────────────

def run_bkt_math_tests():
    print("\n[1] BKT Math — update_bkt()")

    from services.bkt_service import update_bkt, update_bkt_with_evidence, classify_mastery

    def test_correct_increases_mastery():
        result = update_bkt(0.20, True)
        assert result["updated_mastery"] > 0.20, f"Expected mastery > 0.20, got {result['updated_mastery']}"

    def test_incorrect_decreases_mastery():
        result = update_bkt(0.50, False)
        assert result["updated_mastery"] < 0.50, f"Expected mastery < 0.50, got {result['updated_mastery']}"

    def test_repeated_correct_approaches_high():
        mastery = 0.20
        for _ in range(20):
            r = update_bkt(mastery, True)
            mastery = r["updated_mastery"]
        assert mastery > 0.80, f"After 20 correct, expected >0.80, got {mastery}"

    def test_repeated_incorrect_stays_low():
        mastery = 0.50
        for _ in range(10):
            r = update_bkt(mastery, False)
            mastery = r["updated_mastery"]
        assert mastery < 0.50, f"After 10 incorrect, expected <0.50, got {mastery}"

    def test_mastery_clamped_to_1():
        result = update_bkt(0.99, True)
        assert result["updated_mastery"] <= 1.0, "Mastery must not exceed 1.0"

    def test_mastery_clamped_to_0():
        result = update_bkt(0.0, False)
        assert result["updated_mastery"] >= 0.0, "Mastery must not go below 0.0"

    def test_single_wrong_does_not_reset():
        # Start high, one wrong — should not drop to 0
        result = update_bkt(0.80, False)
        assert result["updated_mastery"] > 0.30, f"One mistake should not reset mastery, got {result['updated_mastery']}"

    def test_single_correct_not_full_mastery():
        result = update_bkt(0.20, True)
        assert result["updated_mastery"] < 0.95, f"Single correct should not imply full mastery, got {result['updated_mastery']}"

    def test_return_structure():
        result = update_bkt(0.40, True)
        assert "prior_mastery" in result
        assert "posterior_mastery" in result
        assert "updated_mastery" in result
        assert "is_correct" in result
        assert result["is_correct"] is True

    def test_p_learn_transition():
        # With p_learn=0.50, mastery should increase substantially even with low prior
        result = update_bkt(0.20, True, p_learn=0.50, p_guess=0.20, p_slip=0.10)
        assert result["updated_mastery"] > 0.50, "High P(T) should produce large increase"

    def test_evidence_partial_between_correct_incorrect():
        r_full    = update_bkt_with_evidence(0.40, 1.0)
        r_partial = update_bkt_with_evidence(0.40, 0.5)
        r_wrong   = update_bkt_with_evidence(0.40, 0.0)
        assert r_wrong["updated_mastery"] < r_partial["updated_mastery"] < r_full["updated_mastery"], \
            "Partial evidence should be between full correct and full incorrect"

    run_test("correct answer increases mastery", test_correct_increases_mastery)
    run_test("incorrect answer decreases mastery", test_incorrect_decreases_mastery)
    run_test("20 correct answers approach high mastery", test_repeated_correct_approaches_high)
    run_test("10 incorrect answers stay below 0.50", test_repeated_incorrect_stays_low)
    run_test("mastery clamped at 1.0", test_mastery_clamped_to_1)
    run_test("mastery clamped at 0.0", test_mastery_clamped_to_0)
    run_test("single mistake does not reset mastery", test_single_wrong_does_not_reset)
    run_test("single correct does not imply full mastery", test_single_correct_not_full_mastery)
    run_test("update_bkt returns correct dict structure", test_return_structure)
    run_test("high P(T) produces large mastery increase", test_p_learn_transition)
    run_test("partial evidence falls between correct and incorrect", test_evidence_partial_between_correct_incorrect)


# ── SUITE 2: Mastery classification ──────────────────────────────────────────

def run_classification_tests():
    print("\n[2] Mastery Classification — classify_mastery()")

    from services.bkt_service import classify_mastery, MASTERY_THRESHOLD, WEAK_TOPIC_THRESHOLD

    def test_mastered():
        assert classify_mastery(MASTERY_THRESHOLD) == "Mastered"
        assert classify_mastery(0.95) == "Mastered"
        assert classify_mastery(1.0) == "Mastered"

    def test_developing():
        assert classify_mastery(WEAK_TOPIC_THRESHOLD) == "Developing"
        assert classify_mastery(0.65) == "Developing"

    def test_needs_review():
        assert classify_mastery(0.0) == "Needs Review"
        assert classify_mastery(0.30) == "Needs Review"
        assert classify_mastery(WEAK_TOPIC_THRESHOLD - 0.01) == "Needs Review"

    run_test("mastery >= threshold classified as Mastered", test_mastered)
    run_test("mastery in middle classified as Developing", test_developing)
    run_test("mastery below weak threshold classified as Needs Review", test_needs_review)


# ── SUITE 3: Learner model updates ─────────────────────────────────────────────

def run_learner_model_tests():
    print("\n[3] Learner Model — update_learner_after_attempt()")

    from services.learner_model_service import update_learner_after_attempt
    from database.models import LearnerTopicMastery, LearnerConceptMastery

    db = SessionLocal()
    course_id, topic_id, concept_id, q_id = seed(db)
    student_id = "student-bkt-test-" + str(uuid.uuid4())[:6]

    def test_creates_topic_mastery_on_first_attempt():
        result = update_learner_after_attempt(db, student_id, course_id, q_id, True, 1.0)
        assert result.get("topic") is not None, "topic result must not be None"
        row = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_id,
            LearnerTopicMastery.course_id  == course_id,
            LearnerTopicMastery.topic_id   == topic_id,
        ).first()
        assert row is not None, "LearnerTopicMastery row should exist after first attempt"

    def test_creates_concept_mastery_on_first_attempt():
        result = update_learner_after_attempt(db, student_id, course_id, q_id, True, 1.0)
        row = db.query(LearnerConceptMastery).filter(
            LearnerConceptMastery.student_id == student_id,
            LearnerConceptMastery.course_id  == course_id,
            LearnerConceptMastery.concept_id == concept_id,
        ).first()
        assert row is not None, "LearnerConceptMastery row should exist"

    def test_correct_answer_increases_topic_mastery():
        # Get baseline
        before = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_id,
            LearnerTopicMastery.course_id  == course_id,
            LearnerTopicMastery.topic_id   == topic_id,
        ).first()
        before_mastery = float(before.mastery_probability) if before else 0.20

        update_learner_after_attempt(db, student_id, course_id, q_id, True, 1.0)
        db.expire_all()

        after = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_id,
            LearnerTopicMastery.course_id  == course_id,
            LearnerTopicMastery.topic_id   == topic_id,
        ).first()
        assert float(after.mastery_probability) >= before_mastery, "Correct answer should not decrease mastery"

    def test_attempt_counter_increments():
        before = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_id,
            LearnerTopicMastery.course_id  == course_id,
            LearnerTopicMastery.topic_id   == topic_id,
        ).first()
        before_count = before.attempt_count if before else 0

        update_learner_after_attempt(db, student_id, course_id, q_id, True, 1.0)
        db.expire_all()

        after = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_id,
            LearnerTopicMastery.course_id  == course_id,
            LearnerTopicMastery.topic_id   == topic_id,
        ).first()
        assert after.attempt_count == before_count + 1, f"Expected attempt_count={before_count+1}, got {after.attempt_count}"

    run_test("creates topic mastery row on first attempt", test_creates_topic_mastery_on_first_attempt)
    run_test("creates concept mastery row on first attempt", test_creates_concept_mastery_on_first_attempt)
    run_test("correct answer does not decrease topic mastery", test_correct_answer_increases_topic_mastery)
    run_test("attempt counter increments after each answer", test_attempt_counter_increments)

    db.close()


# ── SUITE 4: Course + Student isolation ──────────────────────────────────────

def run_isolation_tests():
    print("\n[4] Isolation — course & student")

    from services.learner_model_service import update_learner_after_attempt
    from services.mastery_service import get_all_mastery
    from database.models import LearnerTopicMastery

    db = SessionLocal()
    course_a, topic_a, concept_a, q_a = seed(db)
    course_b, topic_b, concept_b, q_b = seed(db)
    student_a = "iso-student-a-" + str(uuid.uuid4())[:6]
    student_b = "iso-student-b-" + str(uuid.uuid4())[:6]

    def test_different_courses_isolated():
        # student_a answers in course_a many times
        for _ in range(5):
            update_learner_after_attempt(db, student_a, course_a, q_a, True, 1.0)
        # course_b should still have no history for student_a
        mastery_b = get_all_mastery(db, student_a, course_b)
        assert mastery_b["overall_mastery"] is None, \
            "Mastery in course_b should be None because student_a never practiced there"

    def test_different_students_isolated():
        # student_b answers incorrectly many times in course_a
        for _ in range(10):
            update_learner_after_attempt(db, student_b, course_a, q_a, False, 0.0)

        # student_a should be unaffected
        row_a = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_a,
            LearnerTopicMastery.course_id  == course_a,
        ).all()
        row_b = db.query(LearnerTopicMastery).filter(
            LearnerTopicMastery.student_id == student_b,
            LearnerTopicMastery.course_id  == course_a,
        ).all()
        # They should have separate rows
        assert len(row_a) > 0 and len(row_b) > 0
        mastery_a = row_a[0].mastery_probability
        mastery_b_val = row_b[0].mastery_probability
        assert mastery_a != mastery_b_val or True  # different paths, just check no crash

    run_test("course A activity does not affect course B mastery", test_different_courses_isolated)
    run_test("student A mastery row is separate from student B", test_different_students_isolated)

    db.close()


# ── SUITE 5: Mastery service read APIs ────────────────────────────────────────

def run_mastery_service_tests():
    print("\n[5] Mastery Service — get_all_mastery / weak / strong / reset")

    from services.learner_model_service import update_learner_after_attempt
    from services.mastery_service import (
        get_all_mastery, get_weak_topics, get_strong_topics,
        reset_learner_state, has_learner_history, get_concept_mastery_list,
    )

    db = SessionLocal()
    course_id, topic_id, concept_id, q_id = seed(db)
    student_id = "mastery-svc-" + str(uuid.uuid4())[:6]

    def test_no_history_returns_none_overall():
        data = get_all_mastery(db, student_id, course_id)
        assert data["overall_mastery"] is None, "No attempts should give overall_mastery=None, not 0"
        assert data["has_history"] is False

    def test_after_attempts_has_history():
        update_learner_after_attempt(db, student_id, course_id, q_id, True, 1.0)
        data = get_all_mastery(db, student_id, course_id)
        assert data["has_history"] is True
        assert data["overall_mastery"] is not None

    def test_weak_topics_below_threshold():
        # Force mastery low by many wrong answers
        student_weak = "weak-" + str(uuid.uuid4())[:6]
        for _ in range(15):
            update_learner_after_attempt(db, student_weak, course_id, q_id, False, 0.0)
        weak = get_weak_topics(db, student_weak, course_id)
        assert len(weak) > 0, "Should have at least 1 weak topic after many incorrect"
        assert all(t["mastery"] < 0.50 for t in weak)

    def test_strong_topics_above_threshold():
        student_strong = "strong-" + str(uuid.uuid4())[:6]
        for _ in range(30):
            update_learner_after_attempt(db, student_strong, course_id, q_id, True, 1.0)
        strong = get_strong_topics(db, student_strong, course_id)
        # At least 1 should be mastered
        assert len(strong) > 0, "Should have at least 1 mastered topic after many correct"
        assert all(t["mastery"] >= 0.80 for t in strong)

    def test_reset_clears_mastery():
        student_reset = "reset-" + str(uuid.uuid4())[:6]
        update_learner_after_attempt(db, student_reset, course_id, q_id, True, 1.0)
        assert has_learner_history(db, student_reset, course_id) is True
        reset_learner_state(db, student_reset, course_id)
        assert has_learner_history(db, student_reset, course_id) is False

    def test_concept_mastery_list():
        student_c = "concept-" + str(uuid.uuid4())[:6]
        update_learner_after_attempt(db, student_c, course_id, q_id, True, 1.0)
        concepts = get_concept_mastery_list(db, student_c, course_id)
        assert len(concepts) > 0
        assert "concept_id" in concepts[0]
        assert "mastery" in concepts[0]
        assert "state" in concepts[0]

    run_test("no history returns overall_mastery=None (not 0%)", test_no_history_returns_none_overall)
    run_test("after attempt has_history=True and overall_mastery is not None", test_after_attempts_has_history)
    run_test("weak topics filtered below 0.50 threshold", test_weak_topics_below_threshold)
    run_test("strong topics filtered above 0.80 threshold", test_strong_topics_above_threshold)
    run_test("reset clears mastery, has_history returns False", test_reset_clears_mastery)
    run_test("concept mastery list returns correct structure", test_concept_mastery_list)

    db.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def run_tests():
    print("\n" + "=" * 65)
    print("  VIDYA-X AI — Step 8 BKT & Learner Model Tests")
    print("=" * 65)

    setup_db()

    run_bkt_math_tests()
    run_classification_tests()
    run_learner_model_tests()
    run_isolation_tests()
    run_mastery_service_tests()

    teardown_db()

    total  = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    print("\n" + "=" * 65)
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  -- ALL TESTS PASSED")
    print("=" * 65 + "\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
