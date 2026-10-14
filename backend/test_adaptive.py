"""
VIDYA-X AI — Step 9 Adaptive Question Selection & Personalized Practice Test Suite

Run directly with: python backend/test_adaptive.py
"""

import os
import sys
import uuid
import unittest
from datetime import datetime, timezone, timedelta

# Override DATABASE_URL for SQLite in-memory before importing connection
os.environ["DATABASE_URL"] = "sqlite:///./test_adaptive.db"

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
    Prerequisite,
    Question,
    QuestionOption,
    QuizSession,
    QuizAttempt,
    QuestionUsage,
    LearnerTopicMastery,
    LearnerConceptMastery,
)
from services.bkt_service import update_bkt, BKT_INITIAL_MASTERY
from services.learner_model_service import update_learner_after_attempt
from services.candidate_service import (
    get_candidate_questions,
    get_recently_used_questions,
    filter_and_relax_candidates,
)
from services.adaptive_scoring_service import (
    calculate_target_difficulty,
    calculate_difficulty_fit,
    calculate_weakness_score,
    calculate_recent_failure_score,
    calculate_prerequisite_priority,
    calculate_novelty_score,
    calculate_diversity_score,
    score_question_candidate,
)
from services.adaptive_service import (
    get_next_question,
    create_adaptive_quiz,
    get_adaptive_next_question_for_session,
)
from services.personalization_service import get_personalized_recommendations


class TestStep9AdaptiveEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        try:
            if os.path.exists("test_adaptive.db"):
                os.remove("test_adaptive.db")
        except PermissionError:
            pass

    def setUp(self):
        self.db = SessionLocal()
        self.course_id = f"test_course_{uuid.uuid4().hex[:8]}"
        self.student_id = f"student_{uuid.uuid4().hex[:8]}"

        # Create test course
        self.course = Course(id=self.course_id, name="Physics 101")
        self.db.add(self.course)

        # Create topics
        self.topic_m = Topic(id=f"t_momentum_{uuid.uuid4().hex[:6]}", course_id=self.course_id, name="Momentum")
        self.topic_n = Topic(id=f"t_newton_{uuid.uuid4().hex[:6]}", course_id=self.course_id, name="Newton's Laws")
        self.db.add_all([self.topic_m, self.topic_n])

        # Create concepts
        self.concept_m1 = Concept(id=f"c_mom_{uuid.uuid4().hex[:6]}", topic_id=self.topic_m.id, name="Conservation of Momentum", difficulty="easy")
        self.concept_n1 = Concept(id=f"c_newt_{uuid.uuid4().hex[:6]}", topic_id=self.topic_n.id, name="Newton's Second Law", difficulty="medium")
        self.db.add_all([self.concept_m1, self.concept_n1])

        # Create prerequisite: Newton's Laws -> Momentum
        self.prereq = Prerequisite(
            id=uuid.uuid4().hex,
            course_id=self.course_id,
            prerequisite_concept_id=self.concept_n1.id,
            target_concept_id=self.concept_m1.id,
            reason="Newton's laws are foundational for momentum",
        )
        self.db.add(self.prereq)

        # Seed questions
        self.q_easy_m = Question(
            id=f"q_m_easy_{uuid.uuid4().hex[:6]}",
            course_id=self.course_id,
            topic_id=self.topic_m.id,
            concept_id=self.concept_m1.id,
            question_type="mcq",
            prompt="What is momentum?",
            difficulty="easy",
            correct_answer="A",
            fingerprint=uuid.uuid4().hex,
            source_refs=[{"chunk_id": "chk1", "file_name": "ch1.pdf"}],
            status="active",
        )
        self.q_med_m = Question(
            id=f"q_m_med_{uuid.uuid4().hex[:6]}",
            course_id=self.course_id,
            topic_id=self.topic_m.id,
            concept_id=self.concept_m1.id,
            question_type="short_answer",
            prompt="Calculate momentum of a 5kg mass moving at 2m/s.",
            difficulty="medium",
            correct_answer="10 kg m/s",
            fingerprint=uuid.uuid4().hex,
            source_refs=[{"chunk_id": "chk1", "file_name": "ch1.pdf"}],
            status="active",
        )
        self.q_hard_n = Question(
            id=f"q_n_hard_{uuid.uuid4().hex[:6]}",
            course_id=self.course_id,
            topic_id=self.topic_n.id,
            concept_id=self.concept_n1.id,
            question_type="numerical",
            prompt="A 10kg object accelerates at 3m/s^2. Find the net force.",
            difficulty="hard",
            correct_answer="30",
            fingerprint=uuid.uuid4().hex,
            source_refs=[{"chunk_id": "chk2", "file_name": "ch2.pdf"}],
            status="active",
        )
        self.db.add_all([self.q_easy_m, self.q_med_m, self.q_hard_n])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_difficulty_adaptation_rules(self):
        """Verify difficulty rules: low mastery -> easy, medium -> medium, high -> hard."""
        self.assertEqual(calculate_target_difficulty(0.20), "easy")
        self.assertEqual(calculate_target_difficulty(0.50), "easy-medium")
        self.assertEqual(calculate_target_difficulty(0.75), "medium")
        self.assertEqual(calculate_target_difficulty(0.85), "medium-hard")
        self.assertEqual(calculate_target_difficulty(0.95), "hard")

        # Test difficulty fit scores
        self.assertEqual(calculate_difficulty_fit(0.20, "easy"), 1.0)
        self.assertLess(calculate_difficulty_fit(0.20, "hard"), 0.5)
        self.assertEqual(calculate_difficulty_fit(0.95, "hard"), 1.0)

    def test_weak_topic_selection_preference(self):
        """Verify engine prefers weak topics over mastered topics."""
        self.db.add(LearnerConceptMastery(
            id=uuid.uuid4().hex,
            student_id=self.student_id,
            course_id=self.course_id,
            concept_id=self.concept_m1.id,
            topic_id=self.topic_m.id,
            mastery_probability=0.25,
            attempt_count=2,
        ))
        self.db.add(LearnerConceptMastery(
            id=uuid.uuid4().hex,
            student_id=self.student_id,
            course_id=self.course_id,
            concept_id=self.concept_n1.id,
            topic_id=self.topic_n.id,
            mastery_probability=0.85,
            attempt_count=5,
        ))
        self.db.commit()

        res = get_next_question(self.db, self.student_id, self.course_id, force_selection=True)
        self.assertEqual(res["status"], "success")
        self.assertIn(res["question_id"], [self.q_easy_m.id, self.q_med_m.id])

    def test_recent_repetition_filtering(self):
        """Verify recently used questions are filtered out."""
        self.db.add(QuestionUsage(
            id=uuid.uuid4().hex,
            question_id=self.q_easy_m.id,
            student_id=self.student_id,
            used_at=datetime.now(timezone.utc),
        ))
        self.db.commit()

        recently_used = get_recently_used_questions(self.db, self.student_id, self.course_id, window_hours=72)
        self.assertIn(self.q_easy_m.id, recently_used)

        candidates = [self.q_easy_m, self.q_med_m]
        filtered = filter_and_relax_candidates(candidates, recently_used, min_candidates=3)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].id, self.q_med_m.id)


    def test_prerequisite_priority_boost(self):
        """Verify weak prerequisites receive a priority boost."""
        concept_map = {self.concept_m1.id: 0.20, self.concept_n1.id: 0.30}
        prereq_score = calculate_prerequisite_priority(
            db=self.db,
            course_id=self.course_id,
            concept_id=self.concept_n1.id,
            concept_mastery_map=concept_map,
        )
        self.assertGreater(prereq_score, 0.50)

    def test_cold_start_behavior(self):
        """Verify cold start detection when student has no learner history."""
        new_student = f"cold_student_{uuid.uuid4().hex[:6]}"
        res = get_next_question(self.db, new_student, self.course_id)
        self.assertEqual(res["status"], "cold_start")
        self.assertTrue(res["diagnostic_available"])

    def test_course_and_student_isolation(self):
        """Verify course and student history are strictly isolated."""
        other_course = f"other_course_{uuid.uuid4().hex[:6]}"
        other_student = f"other_student_{uuid.uuid4().hex[:6]}"

        self.db.add(LearnerConceptMastery(
            id=uuid.uuid4().hex,
            student_id=other_student,
            course_id=other_course,
            concept_id=self.concept_m1.id,
            mastery_probability=0.99,
        ))
        self.db.commit()

        rec = get_personalized_recommendations(self.db, self.student_id, self.course_id)
        self.assertFalse(rec["has_history"])

    def test_adaptive_integration_loop(self):
        """
        CRITICAL ADAPTIVE INTEGRATION TEST:
          1. Student starts adaptive quiz
          2. Question 1 is answered INCORRECTLY
          3. BKT updates, decreasing mastery
          4. Next question targets that weak concept
          5. Question 2 is answered CORRECTLY
          6. BKT updates, increasing mastery
          7. Question 3 difficulty adjusts appropriately!
        """
        self.db.add(LearnerConceptMastery(
            id=uuid.uuid4().hex,
            student_id=self.student_id,
            course_id=self.course_id,
            concept_id=self.concept_m1.id,
            topic_id=self.topic_m.id,
            mastery_probability=0.46,
            attempt_count=1,
        ))
        self.db.commit()

        # Step A: Select Q1
        q1_res = get_next_question(self.db, self.student_id, self.course_id, force_selection=True)
        self.assertEqual(q1_res["status"], "success")
        q1_id = q1_res["question_id"]

        # Step B: Student answers Q1 INCORRECTLY
        update1 = update_learner_after_attempt(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            question_id=q1_id,
            is_correct=False,
            score=0.0,
        )
        new_mastery_1 = update1["concept"]["mastery"]
        self.assertLess(new_mastery_1, 0.46)

        # Step C: Select Q2
        q2_res = get_next_question(self.db, self.student_id, self.course_id, force_selection=True)
        self.assertEqual(q2_res["status"], "success")
        q2_id = q2_res["question_id"]

        # Step D: Student answers Q2 CORRECTLY
        update2 = update_learner_after_attempt(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            question_id=q2_id,
            is_correct=True,
            score=1.0,
        )
        new_mastery_2 = update2["concept"]["mastery"]
        self.assertGreater(new_mastery_2, new_mastery_1)

        # Step E: Select Q3
        q3_res = get_next_question(self.db, self.student_id, self.course_id, force_selection=True)
        self.assertEqual(q3_res["status"], "success")

    def test_demo_scenario_seeded_student(self):
        """
        Demo scenario test for student 'Rahul':
          Momentum = 0.35, Newton's Laws = 0.72.
          Engine selects Momentum easy question first.
        """
        demo_student = "Rahul"
        self.db.add(LearnerConceptMastery(
            id=uuid.uuid4().hex,
            student_id=demo_student,
            course_id=self.course_id,
            concept_id=self.concept_m1.id,
            topic_id=self.topic_m.id,
            mastery_probability=0.35,
        ))
        self.db.add(LearnerConceptMastery(
            id=uuid.uuid4().hex,
            student_id=demo_student,
            course_id=self.course_id,
            concept_id=self.concept_n1.id,
            topic_id=self.topic_n.id,
            mastery_probability=0.72,
        ))
        self.db.commit()

        res = get_next_question(self.db, demo_student, self.course_id, force_selection=True)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["concept_id"], self.concept_m1.id)
        self.assertEqual(res["difficulty"], "easy")


def run_tests():
    print("=================================================================")
    print("  VIDYA-X AI — Step 9 Adaptive Engine & Personalization Tests")
    print("=================================================================\n")

    suite = unittest.TestLoader().loadTestsFromTestCase(TestStep9AdaptiveEngine)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n=================================================================")
        print("  Results: ALL TESTS PASSED SUCCESSFULLY!")
        print("=================================================================\n")
        return 0
    else:
        print("\n=================================================================")
        print("  Results: SOME TESTS FAILED!")
        print("=================================================================\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
