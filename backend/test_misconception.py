"""
VIDYA-X AI — Step 10 Misconception Detection & Personalized Remediation Test Suite

Run directly with: python backend/test_misconception.py
"""

import os
import sys
import uuid
import unittest
from datetime import datetime, timezone

# Override DATABASE_URL for SQLite in-memory before importing connection
os.environ["DATABASE_URL"] = "sqlite:///./test_misconception.db"

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import sqlalchemy as sa
from database import models

try:
    for model_class in [models.KnowledgeChunk]:
        for col in model_class.__table__.columns:
            if hasattr(col.type, "__class__") and col.type.__class__.__name__ == "Vector":
                col.type = sa.Text()
except ImportError:
    pass

from database.connection import Base, engine, SessionLocal
from database.models import (
    Course,
    Topic,
    Concept,
    Question,
    QuestionOption,
    QuizSession,
    QuizAttempt,
    MisconceptionRecord,
    MisconceptionEvidence,
    RemediationSession,
    RemediationActivity,
    LearnerTopicMastery,
    LearnerConceptMastery,
)
from services.misconception_detection_service import run_deterministic_checks
from services.misconception_service import (
    detect_misconceptions,
    get_student_misconceptions,
    get_misconception_by_id,
    calculate_misconception_confidence,
)
from services.remediation_service import create_remediation
from services.remediation_tracking_service import (
    complete_remediation_activity,
    evaluate_remediation_outcome,
    get_student_remediations,
    get_remediation_session,
)


class TestStep10MisconceptionsAndRemediation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        # Clean test tables
        self.db.query(RemediationActivity).delete()
        self.db.query(RemediationSession).delete()
        self.db.query(MisconceptionEvidence).delete()
        self.db.query(MisconceptionRecord).delete()
        self.db.query(QuizAttempt).delete()
        self.db.query(QuizSession).delete()
        self.db.query(QuestionOption).delete()
        self.db.query(Question).delete()
        self.db.query(LearnerConceptMastery).delete()
        self.db.query(LearnerTopicMastery).delete()
        self.db.query(Concept).delete()
        self.db.query(Topic).delete()
        self.db.query(Course).delete()
        self.db.commit()

        # Create base test fixtures
        self.course = Course(id="physics-101", name="General Physics I")
        self.db.add(self.course)
        self.db.commit()

        self.topic = Topic(id="topic-kinematics", course_id="physics-101", name="Kinematics", order_index=1)
        self.db.add(self.topic)
        self.db.commit()

        self.concept = Concept(
            id="concept-acceleration",
            topic_id="topic-kinematics",
            name="Acceleration & Gravity",
            description="Gravitational acceleration and vectors",
        )
        self.db.add(self.concept)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. Deterministic Error Detection Tests
    # -------------------------------------------------------------------------

    def test_deterministic_sign_error(self):
        """Test sign error detection when student submits negative instead of positive value (or vice-versa)."""
        q = Question(
            id="q-sign",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="What is downward acceleration due to gravity in m/s^2?",
            correct_answer="-9.8 m/s^2",
            difficulty="easy",
            fingerprint=str(uuid.uuid4()),
        )

        res = run_deterministic_checks(q, "9.8 m/s^2", False, 0.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["error_category"], "sign_direction_error")
        self.assertEqual(res["code"], "sign_convention_error")
        self.assertGreaterEqual(res["confidence"], 0.85)

    def test_deterministic_unit_scale_error(self):
        """Test unit scale error (factor of 1000 mismatch e.g., meters vs kilometers)."""
        q = Question(
            id="q-scale",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="Calculate distance in meters.",
            correct_answer="5000 m",
            difficulty="medium",
            fingerprint=str(uuid.uuid4()),
        )

        res = run_deterministic_checks(q, "5 m", False, 0.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["error_category"], "unit_conversion_error")
        self.assertEqual(res["code"], "unit_conversion_error")

    def test_deterministic_missing_units(self):
        """Test missing units detection when correct answer contains unit but student omits it."""
        q = Question(
            id="q-units",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="Calculate velocity.",
            correct_answer="25 m/s",
            difficulty="easy",
            fingerprint=str(uuid.uuid4()),
        )

        res = run_deterministic_checks(q, "25", False, 0.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["error_category"], "missing_incorrect_units")

    def test_deterministic_minor_calc_error(self):
        """Test minor calculation error detection when numeric response is within 5-15% of target."""
        q = Question(
            id="q-calc",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="Calculate force.",
            correct_answer="100 N",
            difficulty="medium",
            fingerprint=str(uuid.uuid4()),
        )

        res = run_deterministic_checks(q, "93 N", False, 0.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["error_category"], "arithmetic_calculation_error")

    # -------------------------------------------------------------------------
    # 2. Confidence Calculation & Status Lifecycle
    # -------------------------------------------------------------------------

    def test_confidence_and_status_progression(self):
        """Test status transitions: suspected (1 occurrence) -> supported (2+ occurrences) and confidence scaling."""
        conf1, status1 = calculate_misconception_confidence(1, base_confidence=0.60)
        self.assertEqual(status1, "suspected")
        self.assertGreaterEqual(conf1, 0.60)

        conf2, status2 = calculate_misconception_confidence(2, base_confidence=0.60)
        self.assertEqual(status2, "supported")
        self.assertGreater(conf2, conf1)

        conf5, status5 = calculate_misconception_confidence(5, base_confidence=0.60)
        self.assertEqual(status5, "supported")
        self.assertEqual(conf5, 0.95)  # capped at 0.95

    # -------------------------------------------------------------------------
    # 3. Idempotency & Course/Student Isolation
    # -------------------------------------------------------------------------

    def test_detection_idempotency_and_isolation(self):
        """Test that re-running detect_misconceptions on the same attempt does not duplicate evidence."""
        q = Question(
            id="q-iso",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="What is force in N?",
            correct_answer="-50 N",
            difficulty="easy",
            fingerprint=str(uuid.uuid4()),
        )
        self.db.add(q)

        q_session = QuizSession(id="qs-iso", student_id="student_rahul", course_id="physics-101")
        self.db.add(q_session)

        attempt = QuizAttempt(
            id="att-iso-1",
            quiz_session_id="qs-iso",
            question_id="q-iso",
            student_id="student_rahul",
            student_answer="50 N",  # sign error
            is_correct=False,
            score=0.0,
        )
        self.db.add(attempt)
        self.db.commit()

        # First detection pass
        res1 = detect_misconceptions(self.db, student_id="student_rahul", course_id="physics-101", attempt_id="att-iso-1")
        self.assertEqual(res1["status"], "success")
        self.assertTrue(res1["detected"])
        self.assertEqual(len(res1["findings"]), 1)

        mis_id = res1["findings"][0]["id"]

        # Second detection pass on same attempt
        res2 = detect_misconceptions(self.db, student_id="student_rahul", course_id="physics-101", attempt_id="att-iso-1")
        self.assertEqual(res2["status"], "already_analyzed")
        self.assertEqual(len(res2["findings"]), 1)

        # Verify evidence table count is 1
        ev_count = self.db.query(MisconceptionEvidence).filter(MisconceptionEvidence.misconception_id == mis_id).count()
        self.assertEqual(ev_count, 1)

        # Verify student isolation: query for another student returns empty list
        other_list = get_student_misconceptions(self.db, student_id="student_alice", course_id="physics-101")
        self.assertEqual(len(other_list), 0)

        # Query for Rahul returns 1 misconception
        rahul_list = get_student_misconceptions(self.db, student_id="student_rahul", course_id="physics-101")
        self.assertEqual(len(rahul_list), 1)

    # -------------------------------------------------------------------------
    # 4. Remediation Session Generation, Completion & Outcome Evaluation
    # -------------------------------------------------------------------------

    def test_remediation_generation_and_workflow(self):
        """Test generating a grounded remediation session, completing activities, and evaluating cautious outcomes."""
        # Setup active misconception
        rec = MisconceptionRecord(
            id="mis-rem-1",
            student_id="student_rahul",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            misconception_code="sign_error",
            title="Vector Sign Mismatch in Acceleration",
            description="Student ignores negative direction vector for gravitational acceleration.",
            evidence_summary="Submitted +9.8 instead of -9.8 m/s^2",
            confidence=0.85,
            status="supported",
            occurrence_count=2,
        )
        self.db.add(rec)
        self.db.commit()

        # 1. Generate Remediation Session
        sess_data = create_remediation(
            db=self.db,
            misconception_id="mis-rem-1",
            student_id="student_rahul",
            course_id="physics-101",
        )
        self.assertIsNotNone(sess_data)
        self.assertGreaterEqual(len(sess_data["activities"]), 3)

        sess_id = sess_data["session_id"]
        full_sess_start = get_remediation_session(self.db, session_id=sess_id)

        # 2. Complete Activities
        for act in full_sess_start["activities"]:
            act_id = act["activity_id"]
            comp_res = complete_remediation_activity(
                db=self.db,
                session_id=sess_id,
                activity_id=act_id,
                student_id="student_rahul",
            )
            self.assertEqual(comp_res.get("session_id"), sess_id)

        # Check session completion status
        full_sess = get_remediation_session(self.db, session_id=sess_id)
        self.assertEqual(full_sess["status"], "completed")

        # 3. Evaluate Remediation Outcome
        # Set up a post-remediation quiz attempt with correct answer to test cautious outcome evaluation
        q_post = Question(
            id="q-post-1",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="What is acceleration vector in free fall?",
            correct_answer="-9.8 m/s^2",
            difficulty="medium",
            fingerprint=str(uuid.uuid4()),
        )
        self.db.add(q_post)

        qs_post = QuizSession(id="qs-post", student_id="student_rahul", course_id="physics-101")
        self.db.add(qs_post)

        att_post = QuizAttempt(
            id="att-post-1",
            quiz_session_id="qs-post",
            question_id="q-post-1",
            student_id="student_rahul",
            student_answer="-9.8 m/s^2",
            is_correct=True,
            score=1.0,
        )
        self.db.add(att_post)

        # Set learner BKT concept mastery to high
        cm = LearnerConceptMastery(
            id=str(uuid.uuid4()),
            student_id="student_rahul",
            course_id="physics-101",
            concept_id="concept-acceleration",
            mastery_probability=0.90,
        )
        self.db.add(cm)
        self.db.commit()

        outcome = evaluate_remediation_outcome(
            db=self.db,
            student_id="student_rahul",
            course_id="physics-101",
            session_id=sess_id,
        )
        self.assertIn("outcome_status", outcome)

    # -------------------------------------------------------------------------
    # 5. Full End-to-End Demo Scenario: Student Rahul
    # -------------------------------------------------------------------------

    def test_demo_scenario_rahul_end_to_end(self):
        """
        End-to-end integration test matching Step 10 user scenario:
          - Rahul answers force/acceleration question incorrectly.
          - System detects misconception (sign/unit error).
          - Generates grounded remediation session.
          - Rahul completes remediation and practice.
          - Outcome evaluation cautious transition.
        """
        # Question
        q_demo = Question(
            id="q-demo-gravity",
            course_id="physics-101",
            topic_id="topic-kinematics",
            concept_id="concept-acceleration",
            question_type="numerical",
            prompt="A ball is dropped from a height. What is its acceleration vector in m/s^2?",
            correct_answer="-9.8 m/s^2",
            difficulty="easy",
            fingerprint=str(uuid.uuid4()),
        )
        self.db.add(q_demo)

        qs_demo = QuizSession(id="qs-demo", student_id="student_rahul", course_id="physics-101")
        self.db.add(qs_demo)

        att_demo = QuizAttempt(
            id="att-demo-1",
            quiz_session_id="qs-demo",
            question_id="q-demo-gravity",
            student_id="student_rahul",
            student_answer="9.8 m/s^2",
            is_correct=False,
            score=0.0,
        )
        self.db.add(att_demo)
        self.db.commit()

        # 1. Detection
        det = detect_misconceptions(self.db, student_id="student_rahul", course_id="physics-101", attempt_id="att-demo-1")
        self.assertTrue(det["detected"])
        mis_id = det["findings"][0]["id"]
        self.assertIn(det["findings"][0]["status"], ["suspected", "supported"])

        # 2. Remediation
        rem_sess = create_remediation(self.db, misconception_id=mis_id, student_id="student_rahul", course_id="physics-101")
        sess_id = rem_sess["session_id"]
        self.assertIsNotNone(sess_id)

        full_sess = get_remediation_session(self.db, session_id=sess_id)

        # 3. Complete all activities
        for activity in full_sess["activities"]:
            complete_remediation_activity(
                db=self.db,
                session_id=sess_id,
                activity_id=activity["activity_id"],
                student_id="student_rahul",
            )

        # 4. Verify outcome
        outcome = evaluate_remediation_outcome(self.db, student_id="student_rahul", course_id="physics-101", session_id=sess_id)
        self.assertIn("outcome_status", outcome)


if __name__ == "__main__":
    unittest.main()
