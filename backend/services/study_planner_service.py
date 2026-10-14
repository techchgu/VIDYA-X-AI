"""
VIDYA-X AI — Intelligent Study Planner Service (Step 12)

Generates personalized 7- or 14-day study plans for a student based on:
  - Course topics and prerequisite graphs
  - BKT topic mastery estimates
  - Recent quiz performance and error signals
  - Active supported misconceptions
  - Due flashcards spaced repetition queue
  - Upcoming exam date and daily study time budget
  - Saved student study preferences
"""

from datetime import datetime, timezone, timedelta
import logging
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import (
    Course,
    Topic,
    StudentStudyPreferences,
    StudyPlan,
    StudyPlanDay,
    StudyPlanTask,
    FlashcardDeck,
    RevisionMaterial,
    RemediationSession,
)
from services.prioritization_service import calculate_topic_priorities
from services.spaced_repetition_service import get_due_flashcards

logger = logging.getLogger(__name__)


def get_or_create_preferences(
    db: Session,
    student_id: str,
    course_id: str,
    daily_minutes_budget: Optional[int] = None,
    exam_date: Optional[datetime] = None,
    preferred_session_minutes: Optional[int] = None,
    selected_topics: Optional[List[str]] = None,
    unavailable_dates: Optional[List[str]] = None,
) -> StudentStudyPreferences:
    """Retrieve or create student study plan preferences, updating with any provided overrides."""
    prefs = (
        db.query(StudentStudyPreferences)
        .filter(
            StudentStudyPreferences.student_id == student_id,
            StudentStudyPreferences.course_id == course_id,
        )
        .first()
    )

    if not prefs:
        prefs_id = str(uuid.uuid4()).replace("-", "")
        prefs = StudentStudyPreferences(
            id=prefs_id,
            student_id=student_id,
            course_id=course_id,
            daily_minutes_budget=daily_minutes_budget or 45,
            exam_date=exam_date,
            preferred_session_minutes=preferred_session_minutes or 15,
            selected_topics=selected_topics,
            unavailable_dates=unavailable_dates or [],
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    else:
        updated = False
        if daily_minutes_budget is not None and daily_minutes_budget > 0:
            prefs.daily_minutes_budget = daily_minutes_budget
            updated = True
        if exam_date is not None:
            prefs.exam_date = exam_date
            updated = True
        if preferred_session_minutes is not None and preferred_session_minutes > 0:
            prefs.preferred_session_minutes = preferred_session_minutes
            updated = True
        if selected_topics is not None:
            prefs.selected_topics = selected_topics
            updated = True
        if unavailable_dates is not None:
            prefs.unavailable_dates = unavailable_dates
            updated = True

        if updated:
            prefs.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(prefs)

    return prefs


def generate_study_plan(
    db: Session,
    student_id: str,
    course_id: str,
    horizon_days: int = 7,
    daily_minutes_budget: Optional[int] = None,
    exam_date: Optional[datetime] = None,
    selected_topics: Optional[List[str]] = None,
    unavailable_dates: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Generate a feasible, prioritized daily and weekly study plan.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course '{course_id}' not found"}

    horizon_days = max(1, min(14, horizon_days))

    # Update or fetch preferences
    prefs = get_or_create_preferences(
        db=db,
        student_id=student_id,
        course_id=course_id,
        daily_minutes_budget=daily_minutes_budget,
        exam_date=exam_date,
        selected_topics=selected_topics,
        unavailable_dates=unavailable_dates,
    )

    budget = prefs.daily_minutes_budget or 45
    effective_exam_date = prefs.exam_date
    unavail_set = set(prefs.unavailable_dates or [])

    # Calculate priorities
    topic_priorities = calculate_topic_priorities(
        db=db,
        student_id=student_id,
        course_id=course_id,
        exam_date=effective_exam_date,
        now=now,
    )

    # Filter by selected topics if specified
    if prefs.selected_topics and len(prefs.selected_topics) > 0:
        sel_set = set(prefs.selected_topics)
        filtered_priorities = [tp for tp in topic_priorities if tp["topic_id"] in sel_set]
        if filtered_priorities:
            topic_priorities = filtered_priorities

    # Fetch due flashcards
    due_flashcards = get_due_flashcards(db, student_id, course_id, limit=50, now=now)

    # Fetch existing decks, revision materials, and remediation sessions for resource linking
    existing_decks = db.query(FlashcardDeck).filter(
        FlashcardDeck.student_id == student_id,
        FlashcardDeck.course_id == course_id,
    ).all()
    deck_by_topic = {d.topic_id: d.id for d in existing_decks if d.topic_id}

    existing_revisions = db.query(RevisionMaterial).filter(
        RevisionMaterial.student_id == student_id,
        RevisionMaterial.course_id == course_id,
    ).all()
    revision_by_topic = {r.topic_id: r.id for r in existing_revisions if r.topic_id}

    existing_remediations = db.query(RemediationSession).filter(
        RemediationSession.student_id == student_id,
        RemediationSession.course_id == course_id,
        RemediationSession.status == "active",
    ).all()
    remediation_by_topic = {r.topic_id: r.id for r in existing_remediations if r.topic_id}

    # Deactivate any previous active plan for this student and course
    previous_plans = db.query(StudyPlan).filter(
        StudyPlan.student_id == student_id,
        StudyPlan.course_id == course_id,
        StudyPlan.status == "active",
    ).all()
    for p in previous_plans:
        p.status = "archived"
        p.updated_at = now
    db.commit()

    # Create new StudyPlan row
    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if effective_exam_date:
        if effective_exam_date.tzinfo is None:
            effective_exam_date = effective_exam_date.replace(tzinfo=timezone.utc)
        exam_start_date = effective_exam_date.replace(hour=0, minute=0, second=0, microsecond=0)
        days_to_exam = (exam_start_date - start_date).days
        if 0 <= days_to_exam < horizon_days:
            horizon_days = max(1, days_to_exam)

    end_date = start_date + timedelta(days=horizon_days)

    plan_id = str(uuid.uuid4()).replace("-", "")
    plan_title = f"{course.name} — Study Plan ({horizon_days} Days)"

    plan_metadata = {
        "horizon_days": horizon_days,
        "daily_minutes_budget": budget,
        "topic_count": len(topic_priorities),
        "due_flashcard_count": len(due_flashcards),
        "exam_date": effective_exam_date.isoformat() if effective_exam_date else None,
    }

    plan = StudyPlan(
        id=plan_id,
        student_id=student_id,
        course_id=course_id,
        title=plan_title,
        start_date=start_date,
        end_date=end_date,
        exam_date=effective_exam_date,
        daily_minutes_budget=budget,
        status="active",
        plan_metadata=plan_metadata,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    db.commit()

    # Distribute tasks across days
    curr_date = start_date
    day_index = 0
    topic_idx = 0

    while curr_date < end_date and day_index < horizon_days:
        date_str = curr_date.strftime("%Y-%m-%d")
        day_id = str(uuid.uuid4()).replace("-", "")

        is_unavailable = date_str in unavail_set
        is_past_exam = (effective_exam_date is not None) and (curr_date > effective_exam_date)

        day_status = "skipped" if (is_unavailable or is_past_exam) else "pending"

        plan_day = StudyPlanDay(
            id=day_id,
            study_plan_id=plan_id,
            scheduled_date=date_str,
            planned_minutes=0,
            status=day_status,
            created_at=now,
        )
        db.add(plan_day)
        db.commit()

        if is_unavailable or is_past_exam:
            curr_date += timedelta(days=1)
            day_index += 1
            continue

        # Schedule tasks for active day up to budget
        day_minutes_used = 0
        scheduled_tasks = []

        # Task 1: Spaced Repetition Flashcards (if due cards exist)
        if due_flashcards and day_minutes_used + 15 <= budget:
            t_id = str(uuid.uuid4()).replace("-", "")
            deck_id = due_flashcards[0]["deck_id"] if due_flashcards else None
            top_id = due_flashcards[0]["topic_id"] if due_flashcards else None
            task = StudyPlanTask(
                id=t_id,
                study_plan_day_id=day_id,
                task_type="flashcard_review",
                title="Active Recall — Flashcard Review Queue",
                description=f"Review {min(15, len(due_flashcards))} due spaced-repetition cards.",
                topic_id=top_id,
                resource_id=deck_id,
                resource_type="flashcard_deck",
                estimated_minutes=15,
                priority_score=0.85,
                priority_level="high",
                priority_reason="Spaced repetition review is due today",
                status="pending",
                created_at=now,
                updated_at=now,
            )
            db.add(task)
            day_minutes_used += 15
            scheduled_tasks.append(task)

        # Task 2: High Priority Topic Revision / Weak Topic
        if topic_priorities and day_minutes_used + 15 <= budget:
            tp = topic_priorities[topic_idx % len(topic_priorities)]
            topic_idx += 1
            t_id = str(uuid.uuid4()).replace("-", "")

            # Determine task type
            if tp.get("active_misconception"):
                ttype = "remediation_activity"
                title = f"Remediate Misconception: {tp['topic_name']}"
                desc = f"Work through targeted remediation for '{tp['active_misconception']}'."
                res_id = remediation_by_topic.get(tp["topic_id"])
                res_type = "remediation_session"
            elif tp.get("weak_prerequisites"):
                ttype = "prerequisite_review"
                title = f"Review Prerequisite: {tp['topic_name']}"
                desc = f"Review foundational concept '{', '.join(tp['weak_prerequisites'])}'."
                res_id = revision_by_topic.get(tp["topic_id"])
                res_type = "revision_material"
            elif not tp["has_history"]:
                ttype = "self_assessment"
                title = f"Diagnostic Assessment: {tp['topic_name']}"
                desc = "Take initial diagnostic questions to establish baseline knowledge."
                res_id = None
                res_type = None
            else:
                ttype = "weak_topic_revision"
                title = f"Revision & Study: {tp['topic_name']}"
                desc = f"Consolidate key concepts grounded in course material. ({tp['priority_reason']})"
                res_id = revision_by_topic.get(tp["topic_id"])
                res_type = "revision_material"

            task = StudyPlanTask(
                id=t_id,
                study_plan_day_id=day_id,
                task_type=ttype,
                title=title,
                description=desc,
                topic_id=tp["topic_id"],
                resource_id=res_id,
                resource_type=res_type,
                estimated_minutes=15,
                priority_score=tp["priority_score"],
                priority_level=tp["priority_level"],
                priority_reason=tp["priority_reason"],
                status="pending",
                created_at=now,
                updated_at=now,
            )
            db.add(task)
            day_minutes_used += 15
            scheduled_tasks.append(task)

        # Task 3: Grounded Practice Quiz
        if day_minutes_used + 15 <= budget and topic_priorities:
            tp_quiz = topic_priorities[(topic_idx + 1) % len(topic_priorities)]
            t_id = str(uuid.uuid4()).replace("-", "")
            task = StudyPlanTask(
                id=t_id,
                study_plan_day_id=day_id,
                task_type="adaptive_quiz",
                title=f"Adaptive Practice Quiz: {tp_quiz['topic_name']}",
                description="Complete 5 adaptive practice questions tailored to your current mastery.",
                topic_id=tp_quiz["topic_id"],
                resource_id=None,
                resource_type="quiz",
                estimated_minutes=15,
                priority_score=tp_quiz["priority_score"],
                priority_level=tp_quiz["priority_level"],
                priority_reason=f"Adaptive practice for {tp_quiz['topic_name']}",
                status="pending",
                created_at=now,
                updated_at=now,
            )
            db.add(task)
            day_minutes_used += 15
            scheduled_tasks.append(task)

        # Update planned minutes for the day
        plan_day.planned_minutes = day_minutes_used
        db.commit()

        curr_date += timedelta(days=1)
        day_index += 1

    return get_active_study_plan(db, student_id, course_id)


def get_active_study_plan(db: Session, student_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current active study plan details."""
    plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.student_id == student_id,
            StudyPlan.course_id == course_id,
            StudyPlan.status == "active",
        )
        .order_by(StudyPlan.created_at.desc())
        .first()
    )

    if not plan:
        return None

    days = (
        db.query(StudyPlanDay)
        .filter(StudyPlanDay.study_plan_id == plan.id)
        .order_by(StudyPlanDay.scheduled_date.asc())
        .all()
    )

    days_data = []
    total_tasks_count = 0
    completed_tasks_count = 0

    for d in days:
        tasks = (
            db.query(StudyPlanTask)
            .filter(StudyPlanTask.study_plan_day_id == d.id)
            .order_by(StudyPlanTask.priority_score.desc())
            .all()
        )

        formatted_tasks = []
        for t in tasks:
            total_tasks_count += 1
            if t.status == "completed":
                completed_tasks_count += 1

            topic_name = "General Course"
            if t.topic_id:
                top_obj = db.query(Topic).filter(Topic.id == t.topic_id).first()
                if top_obj:
                    topic_name = top_obj.name

            formatted_tasks.append({
                "task_id": t.id,
                "task_type": t.task_type,
                "title": t.title,
                "description": t.description,
                "topic_id": t.topic_id,
                "topic_name": topic_name,
                "concept_id": t.concept_id,
                "resource_id": t.resource_id,
                "resource_type": t.resource_type,
                "estimated_minutes": t.estimated_minutes,
                "actual_minutes": t.actual_minutes,
                "priority_score": t.priority_score,
                "priority_level": t.priority_level,
                "priority_reason": t.priority_reason,
                "status": t.status,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            })

        days_data.append({
            "day_id": d.id,
            "scheduled_date": d.scheduled_date,
            "planned_minutes": d.planned_minutes,
            "status": d.status,
            "tasks": formatted_tasks,
        })

    completion_pct = round((completed_tasks_count / float(total_tasks_count) * 100), 1) if total_tasks_count > 0 else 0.0

    return {
        "plan_id": plan.id,
        "student_id": plan.student_id,
        "course_id": plan.course_id,
        "title": plan.title,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "exam_date": plan.exam_date.isoformat() if plan.exam_date else None,
        "daily_minutes_budget": plan.daily_minutes_budget,
        "status": plan.status,
        "plan_metadata": plan.plan_metadata or {},
        "completion_percentage": completion_pct,
        "total_tasks": total_tasks_count,
        "completed_tasks": completed_tasks_count,
        "days": days_data,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def get_today_tasks(db: Session, student_id: str, course_id: str, date_str: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve tasks scheduled for today (or a specific YYYY-MM-DD date)."""
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.student_id == student_id,
            StudyPlan.course_id == course_id,
            StudyPlan.status == "active",
        )
        .order_by(StudyPlan.created_at.desc())
        .first()
    )

    if not plan:
        return {
            "date": date_str,
            "has_plan": False,
            "planned_minutes": 0,
            "tasks": [],
        }

    day = (
        db.query(StudyPlanDay)
        .filter(
            StudyPlanDay.study_plan_id == plan.id,
            StudyPlanDay.scheduled_date == date_str,
        )
        .first()
    )

    if not day:
        return {
            "date": date_str,
            "has_plan": True,
            "planned_minutes": 0,
            "tasks": [],
        }

    tasks = (
        db.query(StudyPlanTask)
        .filter(StudyPlanTask.study_plan_day_id == day.id)
        .order_by(StudyPlanTask.priority_score.desc())
        .all()
    )

    formatted_tasks = []
    for t in tasks:
        topic_name = "General Course"
        if t.topic_id:
            top_obj = db.query(Topic).filter(Topic.id == t.topic_id).first()
            if top_obj:
                topic_name = top_obj.name

        formatted_tasks.append({
            "task_id": t.id,
            "task_type": t.task_type,
            "title": t.title,
            "description": t.description,
            "topic_id": t.topic_id,
            "topic_name": topic_name,
            "concept_id": t.concept_id,
            "resource_id": t.resource_id,
            "resource_type": t.resource_type,
            "estimated_minutes": t.estimated_minutes,
            "actual_minutes": t.actual_minutes,
            "priority_score": t.priority_score,
            "priority_level": t.priority_level,
            "priority_reason": t.priority_reason,
            "status": t.status,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        })

    return {
        "date": date_str,
        "has_plan": True,
        "plan_id": plan.id,
        "planned_minutes": day.planned_minutes,
        "day_status": day.status,
        "tasks": formatted_tasks,
    }
