"""
VIDYA-X AI — Study Plan Tracking Service (Step 12)

Tracks task lifecycle (pending -> in_progress -> completed / skipped / rescheduled / cancelled).
Preserves study activity history and updates daily plan progress without erasing completed tasks.
"""

from datetime import datetime, timezone
import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import (
    StudyPlan,
    StudyPlanDay,
    StudyPlanTask,
)

logger = logging.getLogger(__name__)

VALID_TASK_STATUSES = {"pending", "in_progress", "completed", "skipped", "rescheduled", "cancelled"}


def update_task_status(
    db: Session,
    task_id: str,
    student_id: str,
    status: str,
    scheduled_start: Optional[datetime] = None,
    target_date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a task's status or reschedule it to another date.
    """
    status_clean = (status or "").strip().lower()
    if status_clean not in VALID_TASK_STATUSES:
        return {"error": f"Invalid task status '{status}'. Must be one of: {', '.join(VALID_TASK_STATUSES)}"}

    task = db.query(StudyPlanTask).filter(StudyPlanTask.id == task_id).first()
    if not task:
        return {"error": f"Task '{task_id}' not found"}

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == task.study_plan_day_id).first()
    if not day:
        return {"error": "Associated plan day not found"}

    plan = db.query(StudyPlan).filter(StudyPlan.id == day.study_plan_id).first()
    if not plan or plan.student_id != student_id:
        return {"error": "Task does not belong to specified student"}

    now = datetime.now(timezone.utc)

    if status_clean == "rescheduled" and target_date_str:
        # Find or create target StudyPlanDay
        target_day = (
            db.query(StudyPlanDay)
            .filter(
                StudyPlanDay.study_plan_id == plan.id,
                StudyPlanDay.scheduled_date == target_date_str,
            )
            .first()
        )
        if not target_day:
            t_day_id = str(uuid.uuid4()).replace("-", "")
            target_day = StudyPlanDay(
                id=t_day_id,
                study_plan_id=plan.id,
                scheduled_date=target_date_str,
                planned_minutes=task.estimated_minutes,
                status="pending",
                created_at=now,
            )
            db.add(target_day)
            db.commit()
        else:
            target_day.planned_minutes += task.estimated_minutes
            db.commit()

        task.study_plan_day_id = target_day.id
        task.status = "pending"
    else:
        task.status = status_clean

    if scheduled_start:
        task.scheduled_start = scheduled_start
    if status_clean == "completed" and not task.completed_at:
        task.completed_at = now

    task.updated_at = now
    db.commit()

    # Refresh day status
    _recalculate_day_status(db, day.id)

    return {
        "success": True,
        "task_id": task.id,
        "status": task.status,
        "updated_at": task.updated_at.isoformat(),
    }


def complete_task(
    db: Session,
    task_id: str,
    student_id: str,
    actual_minutes: Optional[int] = None,
    completion_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Record task completion with actual duration and optional completion feedback metadata.
    """
    task = db.query(StudyPlanTask).filter(StudyPlanTask.id == task_id).first()
    if not task:
        return {"error": f"Task '{task_id}' not found"}

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == task.study_plan_day_id).first()
    if not day:
        return {"error": "Associated plan day not found"}

    plan = db.query(StudyPlan).filter(StudyPlan.id == day.study_plan_id).first()
    if not plan or plan.student_id != student_id:
        return {"error": "Task does not belong to specified student"}

    now = datetime.now(timezone.utc)
    task.status = "completed"
    task.completed_at = now
    task.actual_minutes = actual_minutes or task.estimated_minutes
    if completion_metadata:
        task.completion_metadata = completion_metadata
    task.updated_at = now

    db.commit()

    _recalculate_day_status(db, day.id)

    return {
        "success": True,
        "task_id": task.id,
        "status": task.status,
        "completed_at": now.isoformat(),
        "actual_minutes": task.actual_minutes,
    }


def _recalculate_day_status(db: Session, day_id: str):
    """Update parent StudyPlanDay status based on child task completion state."""
    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return

    tasks = db.query(StudyPlanTask).filter(StudyPlanTask.study_plan_day_id == day_id).all()
    if not tasks:
        return

    statuses = [t.status for t in tasks]
    if all(s in ["completed", "skipped", "cancelled"] for s in statuses):
        day.status = "completed"
    elif any(s == "completed" for s in statuses):
        day.status = "partial"
    else:
        day.status = "pending"

    db.commit()
