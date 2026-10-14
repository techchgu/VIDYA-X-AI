"""
VIDYA-X AI — Step 12 Study Planner & Spaced Repetition Test Suite

Verifies:
  1. Study plans respect daily time budget.
  2. No tasks are scheduled after the exam date.
  3. Plans without an exam date work as rolling plans.
  4. New students receive balanced diagnostic/introductory plans.
  5. Weak prerequisites boost topic priority.
  6. Missing learner data does not crash or dominate prioritization.
  7. Resolved misconceptions drop priority compared to active ones.
  8. Again, Hard, Good, Easy produce expected relative intervals.
  9. Spaced repetition state updates & history preservation.
 10. Task completion, status updates, and rescheduling logic.
 11. Exam readiness reporting with empirical categories.
 12. Cross-student & cross-course isolation.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
import unittest
import uuid

# Override DATABASE_URL for SQLite before importing connection
os.environ["DATABASE_URL"] = "sqlite:///./test_study_plan.db"

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import sqlalchemy as sa
from database import models
from database.connection import Base, engine as db_engine

try:
    for model_class in [models.KnowledgeChunk]:
        for col in model_class.__table__.columns:
            if hasattr(col.type, "__class__") and col.type.__class__.__name__ == "Vector":
                col.type = sa.Text()
except Exception:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Course,
    Topic,
    Concept,
    Prerequisite,
    LearnerTopicMastery,
    QuizAttempt,
    MisconceptionRecord,
    FlashcardDeck,
    Flashcard,
    FlashcardReview,
    StudyPlan,
    StudyPlanDay,
    StudyPlanTask,
    StudentStudyPreferences,
)
from services.spaced_repetition_service import (
    calculate_next_review,
    update_flashcard_spaced_repetition,
    get_due_flashcards,
)
from services.prioritization_service import calculate_topic_priorities
from services.study_planner_service import (
    get_or_create_preferences,
    generate_study_plan,
    get_active_study_plan,
    get_today_tasks,
)
from services.study_plan_tracking_service import update_task_status, complete_task
from services.exam_readiness_service import evaluate_exam_readiness
from services.flashcard_service import record_card_review


class TestStep12StudyPlannerEngine(unittest.TestCase):

    def setUp(self):
        """Set up in-memory SQLite database for testing."""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed test course
        self.course_id = "cs101_algo"
        self.course = Course(id=self.course_id, name="Data Structures & Algorithms")
        self.db.add(self.course)

        # Seed topics
        self.t1 = Topic(id="top_arrays", course_id=self.course_id, name="Arrays & Hashing", order_index=1)
        self.t2 = Topic(id="top_trees", course_id=self.course_id, name="Trees & Graphs", order_index=2)
        self.t3 = Topic(id="top_dp", course_id=self.course_id, name="Dynamic Programming", order_index=3)
        self.db.add_all([self.t1, self.t2, self.t3])

        # Seed concepts
        self.c1 = Concept(id="c_arrays", topic_id=self.t1.id, name="Array Operations")
        self.c2 = Concept(id="c_trees", topic_id=self.t2.id, name="Binary Tree Traversal")
        self.db.add_all([self.c1, self.c2])

        # Seed prerequisite (Arrays is prerequisite of Trees)
        self.prereq = Prerequisite(
            id="p1",
            course_id=self.course_id,
            prerequisite_concept_id=self.c1.id,
            target_concept_id=self.c2.id,
            reason="Arrays needed before Trees",
        )
        self.db.add(self.prereq)
        self.db.commit()

        self.student_id = "student_alex"

    def tearDown(self):
        self.db.close()

    def test_spaced_repetition_intervals(self):
        """Verify Again, Hard, Good, and Easy produce relative interval ordering."""
        now = datetime.now(timezone.utc)

        r_again = calculate_next_review("again", current_interval_days=1.0, review_count=1, now=now)
        r_hard = calculate_next_review("hard", current_interval_days=1.0, review_count=1, now=now)
        r_good = calculate_next_review("good", current_interval_days=1.0, review_count=1, now=now)
        r_easy = calculate_next_review("easy", current_interval_days=1.0, review_count=1, now=now)

        self.assertEqual(r_again["next_interval_days"], 0.0)
        self.assertLess(r_hard["next_interval_days"], r_good["next_interval_days"])
        self.assertLess(r_good["next_interval_days"], r_easy["next_interval_days"])

    def test_spaced_repetition_flashcard_update(self):
        """Verify flashcard review updates spaced repetition columns and preserves review history."""
        deck = FlashcardDeck(
            id="deck1",
            student_id=self.student_id,
            course_id=self.course_id,
            topic_id=self.t1.id,
            title="Array Cards",
        )
        card = Flashcard(
            id="card1",
            deck_id="deck1",
            front="What is array lookup complexity?",
            back="O(1)",
            fingerprint="fp1",
        )
        self.db.add_all([deck, card])
        self.db.commit()

        # Submit review via flashcard service
        res = record_card_review(self.db, card_id="card1", student_id=self.student_id, rating="good")
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["next_review_at"])

        # Check DB state
        updated_card = self.db.query(Flashcard).filter(Flashcard.id == "card1").first()
        self.assertEqual(updated_card.review_count, 1)
        self.assertEqual(updated_card.last_rating, "good")
        self.assertEqual(updated_card.current_interval_days, 3.0)

        # Verify history preservation in FlashcardReview
        rev_count = self.db.query(FlashcardReview).filter(FlashcardReview.flashcard_id == "card1").count()
        self.assertEqual(rev_count, 1)

    def test_topic_prioritization_and_prerequisites(self):
        """Verify topic prioritization gives boost to weak topics and weak prerequisites."""
        # Low BKT mastery for Arrays (prerequisite)
        m1 = LearnerTopicMastery(
            id="m1",
            student_id=self.student_id,
            course_id=self.course_id,
            topic_id=self.t1.id,
            mastery_probability=0.25,
            attempt_count=4,
        )
        self.db.add(m1)
        self.db.commit()

        priorities = calculate_topic_priorities(self.db, self.student_id, self.course_id)
        self.assertGreater(len(priorities), 0)

        # Arrays should have high priority due to low mastery
        arrays_p = next(p for p in priorities if p["topic_id"] == self.t1.id)
        trees_p = next(p for p in priorities if p["topic_id"] == self.t2.id)

        self.assertGreaterEqual(arrays_p["priority_score"], 0.30)
        # Trees should note weak prerequisite
        self.assertIn("Arrays & Hashing", trees_p["weak_prerequisites"])

    def test_misconception_priority_boost(self):
        """Verify active misconception boosts topic priority, while resolved drops it."""
        misc = MisconceptionRecord(
            id="misc1",
            student_id=self.student_id,
            course_id=self.course_id,
            topic_id=self.t3.id,
            misconception_code="dp_overlap",
            title="Overlapping Subproblems Confusion",
            description="Confusing DP with divide-and-conquer",
            status="supported",
        )
        self.db.add(misc)
        self.db.commit()

        priorities = calculate_topic_priorities(self.db, self.student_id, self.course_id)
        dp_p = next(p for p in priorities if p["topic_id"] == self.t3.id)
        self.assertIsNotNone(dp_p["active_misconception"])
        score_active = dp_p["priority_score"]

        # Resolve misconception
        misc.status = "resolved"
        self.db.commit()

        priorities2 = calculate_topic_priorities(self.db, self.student_id, self.course_id)
        dp_p2 = next(p for p in priorities2 if p["topic_id"] == self.t3.id)
        self.assertIsNone(dp_p2["active_misconception"])
        self.assertLess(dp_p2["priority_score"], score_active)

    def test_study_plan_time_budget_and_horizon(self):
        """Verify plan respects daily study-time budget and horizon days."""
        plan_res = generate_study_plan(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            horizon_days=7,
            daily_minutes_budget=30,
        )
        self.assertIsNotNone(plan_res)
        self.assertEqual(plan_res["student_id"], self.student_id)
        self.assertEqual(len(plan_res["days"]), 7)

        for day in plan_res["days"]:
            self.assertLessEqual(day["planned_minutes"], 30)

    def test_study_plan_exam_date_constraint(self):
        """Verify no tasks are scheduled after the exam date."""
        now = datetime.now(timezone.utc)
        exam_dt = now + timedelta(days=3)

        plan_res = generate_study_plan(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            horizon_days=7,
            daily_minutes_budget=45,
            exam_date=exam_dt,
        )
        self.assertIsNotNone(plan_res)
        self.assertEqual(len(plan_res["days"]), 3)

    def test_new_student_starter_plan(self):
        """Verify new student receives balanced introductory/diagnostic tasks."""
        plan_res = generate_study_plan(
            db=self.db,
            student_id="new_student",
            course_id=self.course_id,
            horizon_days=5,
            daily_minutes_budget=45,
        )
        self.assertIsNotNone(plan_res)
        self.assertGreater(len(plan_res["days"]), 0)
        day1 = plan_res["days"][0]
        task_types = [t["task_type"] for t in day1["tasks"]]
        self.assertTrue(any(tt in ["self_assessment", "weak_topic_revision", "adaptive_quiz"] for tt in task_types))

    def test_task_status_lifecycle_and_completion(self):
        """Verify task status update and completion tracking."""
        plan_res = generate_study_plan(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            horizon_days=5,
            daily_minutes_budget=45,
        )
        day1 = plan_res["days"][0]
        task1 = day1["tasks"][0]
        task_id = task1["task_id"]

        # Complete task
        res_c = complete_task(self.db, task_id=task_id, student_id=self.student_id, actual_minutes=20)
        self.assertTrue(res_c["success"])
        self.assertEqual(res_c["actual_minutes"], 20)

        # Check today tasks view
        today_res = get_today_tasks(self.db, self.student_id, self.course_id, date_str=day1["scheduled_date"])
        t_updated = next(t for t in today_res["tasks"] if t["task_id"] == task_id)
        self.assertEqual(t_updated["status"], "completed")

    def test_task_rescheduling(self):
        """Verify rescheduling a task moves it to the target day without deleting history."""
        plan_res = generate_study_plan(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            horizon_days=5,
            daily_minutes_budget=45,
        )
        day1 = plan_res["days"][0]
        day2 = plan_res["days"][1]
        task1 = day1["tasks"][0]

        res = update_task_status(
            db=self.db,
            task_id=task1["task_id"],
            student_id=self.student_id,
            status="rescheduled",
            target_date_str=day2["scheduled_date"],
        )
        self.assertTrue(res["success"])

        # Check that task now belongs to day 2
        task_db = self.db.query(StudyPlanTask).filter(StudyPlanTask.id == task1["task_id"]).first()
        day_db = self.db.query(StudyPlanDay).filter(StudyPlanDay.id == task_db.study_plan_day_id).first()
        self.assertEqual(day_db.scheduled_date, day2["scheduled_date"])

    def test_exam_readiness_insufficient_data(self):
        """Verify readiness returns insufficient_data when attempts are sparse."""
        readiness = evaluate_exam_readiness(self.db, "sparse_student", self.course_id)
        self.assertEqual(readiness["readiness_category"], "insufficient_data")
        self.assertEqual(readiness["confidence_indicator"], "low")

    def test_exam_readiness_eval(self):
        """Verify readiness evaluates reasonably_prepared when mastery and coverage are high."""
        # Seed high masteries across all topics
        for t in [self.t1, self.t2, self.t3]:
            m = LearnerTopicMastery(
                id=f"m_{t.id}",
                student_id=self.student_id,
                course_id=self.course_id,
                topic_id=t.id,
                mastery_probability=0.85,
                attempt_count=5,
            )
            self.db.add(m)
            # Add 5 attempts per topic (15 total)
            for i in range(5):
                att = QuizAttempt(
                    id=str(uuid.uuid4()).replace("-", ""),
                    quiz_session_id="qs1",
                    question_id="q1",
                    student_id=self.student_id,
                    topic_id=t.id,
                    is_correct=1,
                    score=1.0,
                )
                self.db.add(att)
        self.db.commit()

        readiness = evaluate_exam_readiness(self.db, self.student_id, self.course_id)
        self.assertEqual(readiness["readiness_category"], "reasonably_prepared")
        self.assertEqual(readiness["confidence_indicator"], "high")

    def test_cross_student_isolation(self):
        """Verify cross-student data access is prevented."""
        plan_res = generate_study_plan(
            db=self.db,
            student_id=self.student_id,
            course_id=self.course_id,
            horizon_days=5,
        )
        task_id = plan_res["days"][0]["tasks"][0]["task_id"]

        # Attempt to update task as another student
        res_bad = update_task_status(
            db=self.db,
            task_id=task_id,
            student_id="unauthorized_student",
            status="completed",
        )
        self.assertIn("error", res_bad)


if __name__ == "__main__":
    unittest.main()
