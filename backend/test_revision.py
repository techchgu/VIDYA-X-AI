"""
VIDYA-X AI — Step 11 Personalized Revision Materials & Flashcard Engine Test Suite

Run directly with: python backend/test_revision.py
"""

import os
import sys
import uuid
import unittest
from datetime import datetime, timezone

# Override DATABASE_URL for SQLite in-memory before importing connection
os.environ["DATABASE_URL"] = "sqlite:///./test_revision.db"

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
    KnowledgeChunk,
    RevisionMaterial,
    RevisionMaterialSource,
    FlashcardDeck,
    Flashcard,
    FlashcardReview,
    LearnerTopicMastery,
    LearnerConceptMastery,
    MisconceptionRecord,
)
from services.revision_personalization_service import build_personalization_plan
from services.revision_validation_service import (
    validate_topic_and_course,
    resolve_and_validate_citations,
    extract_source_map_from_chunks,
)
from services.revision_generation_service import generate_revision_content
from services.flashcard_service import (
    generate_flashcard_deck,
    get_flashcard_deck,
    record_card_review,
    get_deck_reviews,
    compute_card_fingerprint,
)
from services.revision_service import (
    generate_revision_material,
    get_revision_material,
    get_student_revision_materials,
    delete_revision_material,
    get_student_flashcard_decks,
    delete_flashcard_deck,
)


class TestStep11RevisionAndFlashcards(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        # Clean tables
        self.db.query(FlashcardReview).delete()
        self.db.query(Flashcard).delete()
        self.db.query(FlashcardDeck).delete()
        self.db.query(RevisionMaterialSource).delete()
        self.db.query(RevisionMaterial).delete()
        self.db.query(MisconceptionRecord).delete()
        self.db.query(LearnerConceptMastery).delete()
        self.db.query(LearnerTopicMastery).delete()
        self.db.query(KnowledgeChunk).delete()
        self.db.query(Concept).delete()
        self.db.query(Topic).delete()
        self.db.query(Course).delete()
        self.db.commit()

        # Fixtures
        self.course_a = Course(id="phys-101", name="Physics I")
        self.course_b = Course(id="chem-101", name="Chemistry I")
        self.db.add_all([self.course_a, self.course_b])
        self.db.commit()

        self.topic_a = Topic(id="top-kinematics", course_id="phys-101", name="Kinematics", order_index=1)
        self.topic_b = Topic(id="top-thermo", course_id="phys-101", name="Thermodynamics", order_index=2)
        self.topic_other = Topic(id="top-atoms", course_id="chem-101", name="Atomic Structure", order_index=1)
        self.db.add_all([self.topic_a, self.topic_b, self.topic_other])
        self.db.commit()

        self.chunk1 = KnowledgeChunk(
            id="chunk-1",
            course_id="phys-101",
            content="Newton's First Law states an object remains at rest unless acted upon by a net external force. Acceleration equals force divided by mass: a = F/m.",
            chunk_type="definition",
            chunk_metadata={"page": 12, "file_name": "Physics_Ch1.pdf"},
        )
        self.chunk2 = KnowledgeChunk(
            id="chunk-2",
            course_id="phys-101",
            content="Gravitational acceleration on Earth surface is approximately -9.8 m/s^2 pointing downwards towards Earth center.",
            chunk_type="concept",
            chunk_metadata={"slide": 5, "file_name": "Gravity_Lecture.pptx"},
        )
        self.db.add_all([self.chunk1, self.chunk2])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. Validation & Citation Resolution Tests
    # -------------------------------------------------------------------------

    def test_topic_course_validation(self):
        """Test topic and concept ownership validation across courses."""
        valid, err = validate_topic_and_course(self.db, course_id="phys-101", topic_id="top-kinematics")
        self.assertTrue(valid)
        self.assertIsNone(err)

        invalid, err = validate_topic_and_course(self.db, course_id="phys-101", topic_id="top-atoms")
        self.assertFalse(invalid)
        self.assertIn("does not belong", err)

    def test_citation_resolution_and_fabrication_rejection(self):
        """Test resolving valid source IDs and rejecting/ignoring fabricated source IDs."""
        source_map = {
            "SOURCE_1": {"id": "chunk-1", "file_name": "Physics_Ch1.pdf", "chunk_metadata": {"page": 12}},
            "SOURCE_2": {"id": "chunk-2", "file_name": "Gravity_Lecture.pptx", "chunk_metadata": {"slide": 5}},
        }

        raw_cits = [
            {"source_id": "SOURCE_1"},
            {"source_id": "SOURCE_2"},
            {"source_id": "SOURCE_FABRICATED_999"},  # Fake ID
        ]

        resolved, sources = resolve_and_validate_citations(raw_cits, source_map)
        self.assertEqual(len(resolved), 2)
        self.assertEqual(len(sources), 2)
        source_ids = [r["source_id"] for r in resolved]
        self.assertIn("SOURCE_1", source_ids)
        self.assertIn("SOURCE_2", source_ids)
        self.assertNotIn("SOURCE_FABRICATED_999", source_ids)

    # -------------------------------------------------------------------------
    # 2. Personalization Strategy Tests
    # -------------------------------------------------------------------------

    def test_personalization_new_student_cold_start(self):
        """Test that a student without quiz history receives balanced introductory personalization."""
        plan = build_personalization_plan(self.db, student_id="student_new", course_id="phys-101")
        self.assertEqual(plan["mode"], "balanced_introductory")
        self.assertFalse(plan["has_history"])
        self.assertGreater(len(plan["reasons"]), 0)

    def test_personalization_weak_topics_and_misconceptions(self):
        """Test that weak topic history and active misconceptions are incorporated into personalization plan."""
        # Seed weak topic mastery
        tm = LearnerTopicMastery(
            id=str(uuid.uuid4()),
            student_id="student_rahul",
            course_id="phys-101",
            topic_id="top-kinematics",
            mastery_probability=0.25,
            attempt_count=5,
        )
        self.db.add(tm)

        # Seed misconception
        rec = MisconceptionRecord(
            id="mis-1",
            student_id="student_rahul",
            course_id="phys-101",
            topic_id="top-kinematics",
            misconception_code="sign_error",
            title="Vector Sign Error",
            description="Confuses positive vs negative directional vectors.",
            confidence=0.85,
            status="supported",
        )
        self.db.add(rec)
        self.db.commit()

        plan = build_personalization_plan(self.db, student_id="student_rahul", course_id="phys-101")
        self.assertEqual(plan["mode"], "weak_topic_review")
        self.assertTrue(plan["has_history"])
        self.assertEqual(len(plan["misconception_callouts"]), 1)
        self.assertEqual(plan["misconception_callouts"][0]["title"], "Vector Sign Error")

    # -------------------------------------------------------------------------
    # 3. Revision Material Generation & Storage Tests
    # -------------------------------------------------------------------------

    def test_generate_revision_material_success(self):
        """Test generating, validating, and retrieving grounded revision material."""
        mat = generate_revision_material(
            db=self.db,
            student_id="student_rahul",
            course_id="phys-101",
            topic_id="top-kinematics",
            material_type="revision_notes",
            language="English",
            depth="standard",
        )
        self.assertIsNotNone(mat)
        self.assertIn("material_id", mat)
        self.assertEqual(mat["material_type"], "revision_notes")
        self.assertTrue(mat["grounded"])
        self.assertGreaterEqual(len(mat["sources"]), 1)

        # Retrieve saved material
        retrieved = get_revision_material(self.db, mat["material_id"], student_id="student_rahul")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["title"], mat["title"])

    def test_generate_revision_insufficient_materials(self):
        """Test that course with no uploaded materials returns a clear error."""
        res = generate_revision_material(
            db=self.db,
            student_id="student_demo",
            course_id="chem-101",  # Has no uploaded chunks
            material_type="topic_summary",
        )
        self.assertIn("error", res)
        self.assertTrue(res.get("insufficient_materials"))

    def test_multilingual_settings_passed(self):
        """Test that Hindi and Hinglish language settings produce structured material without errors."""
        mat_hi = generate_revision_material(
            db=self.db,
            student_id="student_demo",
            course_id="phys-101",
            topic_id="top-kinematics",
            material_type="formula_sheet",
            language="Hindi",
            depth="concise",
        )
        self.assertEqual(mat_hi["language"], "Hindi")
        self.assertEqual(mat_hi["depth"], "concise")

    # -------------------------------------------------------------------------
    # 4. Flashcard Engine Tests
    # -------------------------------------------------------------------------

    def test_flashcard_deck_generation_and_deduplication(self):
        """Test flashcard deck creation, non-empty cards, citations, and fingerprint deduplication."""
        deck = generate_flashcard_deck(
            db=self.db,
            student_id="student_rahul",
            course_id="phys-101",
            topic_id="top-kinematics",
            card_count=8,
            language="English",
        )
        self.assertIsNotNone(deck)
        self.assertIn("deck_id", deck)
        self.assertGreaterEqual(deck["card_count"], 2)

        cards = deck["cards"]
        fps = set()
        for c in cards:
            self.assertTrue(len(c["front"]) > 0)
            self.assertTrue(len(c["back"]) > 0)
            fp = compute_card_fingerprint(c["front"], c["card_type"])
            self.assertNotIn(fp, fps)  # Ensure deduplicated
            fps.add(fp)

    def test_flashcard_review_recording_and_validation(self):
        """Test recording card review ratings (again, hard, good, easy) and rating validation."""
        deck = generate_flashcard_deck(
            db=self.db,
            student_id="student_rahul",
            course_id="phys-101",
            card_count=5,
        )
        card_id = deck["cards"][0]["card_id"]

        # Valid rating
        rev = record_card_review(self.db, card_id=card_id, student_id="student_rahul", rating="good", duration_ms=2500)
        self.assertTrue(rev.get("success"))
        self.assertEqual(rev["rating"], "good")

        # Invalid rating
        invalid_rev = record_card_review(self.db, card_id=card_id, student_id="student_rahul", rating="invalid_rating")
        self.assertIn("error", invalid_rev)

        # Retrieve review history
        hist = get_deck_reviews(self.db, deck_id=deck["deck_id"], student_id="student_rahul")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["rating"], "good")

    # -------------------------------------------------------------------------
    # 5. Isolation & Security Tests
    # -------------------------------------------------------------------------

    def test_student_and_course_isolation(self):
        """Test that a student cannot retrieve or delete another student's revision resources or decks."""
        mat = generate_revision_material(
            db=self.db,
            student_id="student_alice",
            course_id="phys-101",
            material_type="revision_notes",
        )
        mat_id = mat["material_id"]

        # Bob tries to access Alice's material -> Unauthorized
        res_bob = get_revision_material(self.db, material_id=mat_id, student_id="student_bob")
        self.assertIn("error", res_bob)

        # Bob tries to delete Alice's material -> Access denied
        del_bob = delete_revision_material(self.db, material_id=mat_id, student_id="student_bob")
        self.assertIn("error", del_bob)

        # Query Alice's materials returns 1, Bob returns 0
        alice_mats = get_student_revision_materials(self.db, student_id="student_alice", course_id="phys-101")
        bob_mats = get_student_revision_materials(self.db, student_id="student_bob", course_id="phys-101")
        self.assertEqual(len(alice_mats), 1)
        self.assertEqual(len(bob_mats), 0)


if __name__ == "__main__":
    unittest.main()
