"""
VIDYA-X AI — Centralized Demo Fixtures & Data Isolation (Step 15)
Provides deterministic sample physics curriculum and records for live presentations.
Completely isolated under course 'course_demo_physics' and student 'student_demo'.
"""

import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from database.models import (
    Course,
    Material,
    Topic,
    Concept,
    Definition,
    KnowledgeChunk,
    Question,
    QuestionOption,
    LearnerTopicMastery,
    LearnerConceptMastery,
    MisconceptionRecord,
    FlashcardDeck,
    Flashcard,
    StudyPlan,
    StudyPlanDay,
    StudyPlanTask,
)
from services.embedding_service import generate_embedding

DEMO_COURSE_ID = "course_demo_physics"
DEMO_STUDENT_ID = "student_demo"


def ensure_demo_fixtures(db: Session) -> Dict[str, Any]:
    """
    Idempotently creates a full, rich course environment covering Newton's Laws of Motion.
    Returns summary statistics.
    """
    # 1. Course
    course = db.get(Course, DEMO_COURSE_ID)
    if not course:
        course = Course(id=DEMO_COURSE_ID, name="Physics: Classical Mechanics & Newton's Laws")
        db.add(course)
        db.flush()

    # 2. Material
    mat_id = "mat_demo_physics_01"
    mat = db.get(Material, mat_id)
    if not mat:
        mat = Material(
            id=mat_id,
            course_id=DEMO_COURSE_ID,
            file_name="Newton_Laws_of_Motion_Lecture_Notes.pdf",
            source_type="pdf",
            file_path="uploads/Newton_Laws_of_Motion_Lecture_Notes.pdf",
            status="processed",
        )
        db.add(mat)
        db.flush()

    # 3. Topics
    topics_data = [
        {"id": "topic_demo_newton_laws", "name": "Newton's Three Laws of Motion", "order": 1},
        {"id": "topic_demo_forces_fbd", "name": "Force, Mass, and Free Body Diagrams", "order": 2},
        {"id": "topic_demo_friction", "name": "Friction and Inclined Planes", "order": 3},
    ]
    for td in topics_data:
        if not db.get(Topic, td["id"]):
            db.add(Topic(id=td["id"], course_id=DEMO_COURSE_ID, name=td["name"], order_index=td["order"]))
    db.flush()

    # 4. Concepts & Definitions
    concepts_data = [
        {
            "id": "concept_demo_inertia",
            "topic_id": "topic_demo_newton_laws",
            "name": "First Law & Inertia",
            "term": "Inertia",
            "definition": "The tendency of an object to resist changes in its state of motion unless acted upon by a net external force.",
        },
        {
            "id": "concept_demo_second_law",
            "topic_id": "topic_demo_forces_fbd",
            "name": "Second Law (F = ma)",
            "term": "Newton's Second Law",
            "definition": "The acceleration of an object is directly proportional to net force and inversely proportional to its mass: F_net = m * a.",
        },
        {
            "id": "concept_demo_friction",
            "topic_id": "topic_demo_friction",
            "name": "Kinetic and Static Friction",
            "term": "Friction Force",
            "definition": "Friction acts parallel to contacting surfaces opposing relative motion: f_k = mu_k * N.",
        },
    ]
    for cd in concepts_data:
        if not db.get(Concept, cd["id"]):
            db.add(Concept(id=cd["id"], topic_id=cd["topic_id"], name=cd["name"], difficulty="medium"))
        if not db.get(Definition, f"def_{cd['id']}"):
            db.add(Definition(id=f"def_{cd['id']}", concept_id=cd["id"], term=cd["term"], definition=cd["definition"]))
    db.flush()

    # 5. Knowledge Chunks with Grounded Text
    chunks_data = [
        {
            "id": "chunk_demo_p01",
            "page": 1,
            "content": (
                "Newton's First Law of Motion states that every object will remain at rest or in uniform motion "
                "in a straight line unless compelled to change its state by the action of an external force. "
                "This property is known as inertia, and an object's mass serves as a quantitative measure of its inertia."
            ),
        },
        {
            "id": "chunk_demo_p02",
            "page": 2,
            "content": (
                "Newton's Second Law defines the relationship between an object's mass m, its acceleration a, "
                "and the net applied force F_net: F_net = m * a. In SI units, force is measured in Newtons (N), "
                "where 1 N = 1 kg * m/s^2. When analyzing multiple forces, always draw a Free Body Diagram (FBD)."
            ),
        },
        {
            "id": "chunk_demo_p03",
            "page": 3,
            "content": (
                "Newton's Third Law states that for every action force, there is an equal and opposite reaction force. "
                "Action-reaction pairs act on different bodies and never cancel each other out on the same body."
            ),
        },
        {
            "id": "chunk_demo_p04",
            "page": 4,
            "content": (
                "Friction is a resistive contact force. Static friction prevents motion up to a maximum threshold: "
                "f_s <= mu_s * N. Once relative motion occurs, kinetic friction acts with constant magnitude: "
                "f_k = mu_k * N, where N is the normal force perpendicular to the surface."
            ),
        },
    ]
    for ch in chunks_data:
        if not db.get(KnowledgeChunk, ch["id"]):
            emb = generate_embedding(ch["content"])
            db.add(KnowledgeChunk(
                id=ch["id"],
                course_id=DEMO_COURSE_ID,
                material_id=mat_id,
                content=ch["content"],
                chunk_type="content_unit",
                embedding=emb,
                chunk_metadata={
                    "file_name": "Newton_Laws_of_Motion_Lecture_Notes.pdf",
                    "source_type": "pdf",
                    "page": ch["page"],
                    "slide": None,
                    "timestamp_start": None,
                    "is_visual": False,
                },
            ))
    db.flush()

    # 6. Seed Learner Mastery for Demo Student
    # Topic 1: Mastered (0.85)
    # Topic 2: Developing (0.62)
    # Topic 3: Weak (0.35)
    tm3 = db.query(LearnerTopicMastery).filter(
        LearnerTopicMastery.student_id == DEMO_STUDENT_ID,
        LearnerTopicMastery.course_id == DEMO_COURSE_ID,
        LearnerTopicMastery.topic_id == "topic_demo_friction",
    ).first()
    if not tm3:
        db.add(LearnerTopicMastery(
            id="ltm_demo_friction",
            student_id=DEMO_STUDENT_ID,
            course_id=DEMO_COURSE_ID,
            topic_id="topic_demo_friction",
            mastery_probability=0.35,
            attempt_count=5,
            correct_count=1,
            incorrect_count=4,
        ))

    # 7. Seed Supported Misconception
    misc = db.query(MisconceptionRecord).filter(
        MisconceptionRecord.student_id == DEMO_STUDENT_ID,
        MisconceptionRecord.course_id == DEMO_COURSE_ID,
    ).first()
    if not misc:
        db.add(MisconceptionRecord(
            id="misc_demo_friction_normal",
            student_id=DEMO_STUDENT_ID,
            course_id=DEMO_COURSE_ID,
            topic_id="topic_demo_friction",
            concept_id="concept_demo_friction",
            misconception_code="normal_force_confusion",
            title="Assuming Normal Force Always Equals mg",
            description="Student incorrectly assumes normal force N = mg on inclined surfaces without accounting for cos(theta).",
            evidence_summary="Observed in 3 consecutive quiz attempts on inclined plane mechanics.",
            confidence=0.88,
            status="supported",
        ))

    db.commit()
    return {
        "success": True,
        "course_id": DEMO_COURSE_ID,
        "student_id": DEMO_STUDENT_ID,
        "message": "Demo physics fixtures successfully populated.",
    }


def reset_demo_fixtures(db: Session) -> Dict[str, Any]:
    """
    Safely resets ONLY demo student and demo course data without touching real student records.
    """
    # Delete demo questions, attempts, mastery, misconceptions, plans
    db.query(MisconceptionRecord).filter(MisconceptionRecord.course_id == DEMO_COURSE_ID).delete()
    db.query(LearnerTopicMastery).filter(LearnerTopicMastery.course_id == DEMO_COURSE_ID).delete()
    db.query(LearnerConceptMastery).filter(LearnerConceptMastery.course_id == DEMO_COURSE_ID).delete()
    db.query(KnowledgeChunk).filter(KnowledgeChunk.course_id == DEMO_COURSE_ID).delete()
    db.query(Definition).filter(Definition.concept_id.like("concept_demo_%")).delete()
    db.query(Concept).filter(Concept.topic_id.like("topic_demo_%")).delete()
    db.query(Topic).filter(Topic.course_id == DEMO_COURSE_ID).delete()
    db.query(Material).filter(Material.course_id == DEMO_COURSE_ID).delete()
    db.query(Course).filter(Course.id == DEMO_COURSE_ID).delete()
    db.commit()

    # Re-seed fresh demo state
    return ensure_demo_fixtures(db)
