"""Task and Step Repository.
Data access layer for tasks, steps, idempotency, and audit events.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.task import Task
from app.db.models.step import TaskStep
from app.db.models.idempotency import IdempotencyRecord
from app.db.models.audit import AuditEvent


class TaskRepository:
    """Async database operations for task entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, task_id: str) -> Optional[Task]:
        stmt = select(Task).where(Task.id == task_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional[Task]:
        stmt = select(Task).where(Task.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_task(
        self,
        task_id: str,
        user_id: str,
        objective: str,
        deadline_at: datetime,
        idempotency_key: Optional[str] = None
    ) -> Task:
        task = Task(
            id=task_id,
            user_id=user_id,
            objective=objective,
            status="SUBMITTED",
            deadline_at=deadline_at,
            idempotency_key=idempotency_key
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def update_task_progress(
        self,
        task_id: str,
        status: str,
        current_node: Optional[str] = None,
        plan_json: Optional[Dict[str, Any]] = None,
        final_report: Optional[str] = None,
        error_summary: Optional[str] = None
    ) -> None:
        values: Dict[str, Any] = {"status": status}
        if current_node is not None:
            values["current_node"] = current_node
        if plan_json is not None:
            values["plan_json"] = plan_json
        if final_report is not None:
            values["final_report"] = final_report
        if error_summary is not None:
            values["error_summary"] = error_summary

        stmt = update(Task).where(Task.id == task_id).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def record_audit_event(
        self,
        task_id: Optional[str],
        user_id: Optional[str],
        action: str,
        resource_type: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        event = AuditEvent(
            task_id=task_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            payload=payload
        )
        self.session.add(event)
        await self.session.flush()
