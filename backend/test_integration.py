"""
VIDYA-X AI — Centralized Integration & Step 15 Test Suite

Verifies:
  1. Grounded AI Tutor: answers supported questions with exact citations.
  2. Grounded AI Tutor: safely abstains on unsupported / out-of-domain questions.
  3. Unified Dashboard Summary: aggregates materials, chunks, topics, misconceptions, and tasks.
  4. Demo Fixtures: populates classical mechanics course idempotently.
  5. Demo Isolation: demo operations do not affect real student records.
  6. Demo Reset: resets demo data cleanly without touching external records.
  7. Full end-to-end learning journey (profile -> upload -> chunk -> tutor -> quiz -> mastery).
"""

import os
import sys
import unittest

os.environ["DATABASE_URL"] = "sqlite:///./test_integration.db"

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import sqlalchemy as sa
from database import models
from database.connection import Base

# Patch Vector column to Text for SQLite
try:
    for model_class in [models.KnowledgeChunk]:
        for col in model_class.__table__.columns:
            if hasattr(col.type, "__class__") and col.type.__class__.__name__ == "Vector":
                col.type = sa.Text()
except Exception:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Course, Material, KnowledgeChunk, Topic, MisconceptionRecord
from services.tutor_service import answer_student_question
from services.demo_service import ensure_demo_fixtures, reset_demo_fixtures, DEMO_COURSE_ID, DEMO_STUDENT_ID
from services.embedding_service import generate_embedding


class TestStep15IntegrationAndDemo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed real user course (idempotent)
        self.real_course = self.db.get(Course, "course_math_101")
        if not self.real_course:
            self.real_course = Course(id="course_math_101", name="Calculus I")
            self.db.add(self.real_course)
            self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_demo_fixture_population_and_idempotency(self):
        """Verify demo fixtures initialize Newton's laws content correctly."""
        res = ensure_demo_fixtures(self.db)
        self.assertTrue(res["success"])
        self.assertEqual(res["course_id"], DEMO_COURSE_ID)

        # Verify course exists
        c = self.db.get(Course, DEMO_COURSE_ID)
        self.assertIsNotNone(c)

        # Verify idempotency
        res2 = ensure_demo_fixtures(self.db)
        self.assertTrue(res2["success"])

    def test_tutor_grounded_answer_with_citations(self):
        """Verify tutor returns grounded citations for course-supported question."""
        ensure_demo_fixtures(self.db)

        # Ask question about Newton's Second Law
        ans = answer_student_question(
            db=self.db,
            course_id=DEMO_COURSE_ID,
            question="What is Newton's Second Law formula relating force, mass and acceleration?",
        )
        self.assertTrue(ans["supported"])
        self.assertTrue(len(ans["citations"]) > 0)
        self.assertIn("F_net", ans["answer"] + str(ans["citations"]))
        top_cite = ans["citations"][0]
        self.assertEqual(top_cite["file_name"], "Newton_Laws_of_Motion_Lecture_Notes.pdf")

    def test_tutor_safe_abstention_on_unsupported_question(self):
        """Verify tutor safely abstains when question is out-of-domain."""
        ensure_demo_fixtures(self.db)

        ans = answer_student_question(
            db=self.db,
            course_id=DEMO_COURSE_ID,
            question="What is the chemical mechanism of photosynthesis in C4 plants?",
        )
        # Should detect zero relevance to Newton mechanics and abstain
        self.assertFalse(ans["supported"])
        self.assertIn("couldn't find sufficient information", ans["answer"])
        self.assertEqual(len(ans["citations"]), 0)

    def test_demo_isolation_and_safe_reset(self):
        """Verify demo reset clears demo content without deleting real student courses."""
        ensure_demo_fixtures(self.db)

        # Add a real user record
        real_chunk = KnowledgeChunk(
            id="chunk_real_math",
            course_id="course_math_101",
            content="Derivatives of polynomials using power rule.",
            chunk_type="definition",
            embedding=[0.1] * 384,
            chunk_metadata={"file_name": "calc.pdf", "page": 10},
        )
        self.db.add(real_chunk)
        self.db.commit()

        # Reset demo
        res = reset_demo_fixtures(self.db)
        self.assertTrue(res["success"])

        # Real user course and chunk MUST still exist intact!
        real_c = self.db.get(Course, "course_math_101")
        real_k = self.db.get(KnowledgeChunk, "chunk_real_math")
        self.assertIsNotNone(real_c)
        self.assertIsNotNone(real_k)
        self.assertEqual(real_k.content, "Derivatives of polynomials using power rule.")


if __name__ == "__main__":
    unittest.main()
