"""Task Orchestration Service.
Bridges FastAPI request ingestion, SQLAlchemy domain models, and LangGraph workflow execution.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.graph.workflow import get_workflow_app
from app.policies.injection_guard import injection_guard
from app.repositories.task_repo import TaskRepository
from app.schemas.task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatus,
    TaskStatusResponse,
    TaskDetailResponse,
)


class TaskService:
    """Manages task submission, background execution, and state synchronization."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TaskRepository(session)

    async def submit_task(
        self,
        request: TaskCreateRequest,
        user_id: str,
        idempotency_key: Optional[str] = None
    ) -> TaskCreateResponse:
        """Submit a new task, performing injection checks, idempotency, and dispatch."""
        # Check idempotency
        if idempotency_key:
            existing = await self.repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Idempotent task request replayed: {existing.id}")
                return TaskCreateResponse(
                    task_id=existing.id,
                    status=TaskStatus(existing.status),
                    created_at=existing.created_at,
                    poll_url=f"/api/v1/tasks/{existing.id}/status"
                )

        # Sanitize prompt against prompt injection attempts
        clean_objective, flagged = injection_guard.inspect_and_sanitize(request.objective)
        if flagged:
            logger.warning("Potential prompt injection pattern detected and sanitized in user objective")

        task_id = str(uuid.uuid4())
        deadline = datetime.now(timezone.utc) + timedelta(seconds=request.max_execution_seconds or settings.DEFAULT_TASK_TIMEOUT_SECONDS)

        # Create task record in app database
        task = await self.repo.create_task(
            task_id=task_id,
            user_id=user_id,
            objective=clean_objective,
            deadline_at=deadline,
            idempotency_key=idempotency_key
        )
        await self.repo.record_audit_event(
            task_id=task_id,
            user_id=user_id,
            action="TASK_SUBMITTED",
            resource_type="task",
            payload={"objective": clean_objective}
        )
        await self.session.commit()

        # Launch graph workflow in background task
        asyncio.create_task(self._run_workflow_async(task_id, user_id, clean_objective, deadline))

        return TaskCreateResponse(
            task_id=task_id,
            status=TaskStatus.SUBMITTED,
            created_at=task.created_at,
            poll_url=f"/api/v1/tasks/{task_id}/status"
        )

    async def _run_workflow_async(
        self,
        task_id: str,
        user_id: str,
        objective: str,
        deadline: datetime
    ) -> None:
        """Execute LangGraph state machine with thread-level persistence."""
        from app.db.session import AsyncSessionLocal

        initial_state = {
            "task_id": task_id,
            "user_id": user_id,
            "objective": objective,
            "status": "SUBMITTED",
            "current_node": "init_task_node",
            "current_step_id": None,
            "plan": None,
            "steps": {},
            "completed_step_ids": [],
            "failed_step_ids": [],
            "step_outputs": {},
            "evidence": [],
            "step_counter": 0,
            "replan_counter": 0,
            "model_call_counter": 0,
            "max_steps": settings.MAX_PLAN_STEPS,
            "max_replans": settings.MAX_REPLANS,
            "deadline_at": deadline.isoformat(),
            "final_report": None,
            "error_summary": None,
            "execution_trace": []
        }

        # Checkpointer thread configuration
        config = {"configurable": {"thread_id": task_id}}

        try:
            workflow_app = await get_workflow_app()
            # Stream execution events and update DB incrementally
            final_state = await workflow_app.ainvoke(initial_state, config=config)

            # Sync final state to DB
            async with AsyncSessionLocal() as session:
                repo = TaskRepository(session)
                await repo.update_task_progress(
                    task_id=task_id,
                    status=final_state.get("status", "COMPLETED"),
                    current_node=final_state.get("current_node"),
                    plan_json=final_state.get("plan"),
                    final_report=final_state.get("final_report"),
                    error_summary=final_state.get("error_summary")
                )
                await repo.record_audit_event(
                    task_id=task_id,
                    user_id=user_id,
                    action="TASK_COMPLETED" if final_state.get("status") == "COMPLETED" else "TASK_FAILED",
                    resource_type="task",
                    payload={"status": final_state.get("status")}
                )
        except Exception as e:
            logger.error(f"Workflow execution failure for task {task_id}: {e}", exc_info=True)
            async with AsyncSessionLocal() as session:
                repo = TaskRepository(session)
                await repo.update_task_progress(
                    task_id=task_id,
                    status="FAILED",
                    error_summary=f"Unhandled system error: {str(e)}"
                )

    async def get_task_status(self, task_id: str, user_id: str) -> Optional[TaskStatusResponse]:
        """Fetch lightweight status for polling clients."""
        task = await self.repo.get_by_id(task_id)
        if not task:
            return None

        # Cross-user isolation check
        if task.user_id != user_id and user_id != "admin-user":
            return None

        total_steps = len(task.plan_json.get("steps", [])) if task.plan_json else 0

        # Query LangGraph checkpointer for current live state if running
        completed_count = 0
        current_node = task.current_node

        workflow_app = await get_workflow_app()
        state_snapshot = await workflow_app.aget_state({"configurable": {"thread_id": task_id}})
        if state_snapshot and state_snapshot.values:
            completed_count = len(state_snapshot.values.get("completed_step_ids", []))
            current_node = state_snapshot.values.get("current_node", current_node)

        return TaskStatusResponse(
            task_id=task.id,
            status=TaskStatus(task.status),
            current_node=current_node,
            completed_steps_count=completed_count,
            total_steps_count=total_steps,
            error_summary=task.error_summary,
            started_at=task.created_at,
            updated_at=task.updated_at,
            deadline_at=task.deadline_at
        )

    async def get_task_detail(self, task_id: str, user_id: str) -> Optional[TaskDetailResponse]:
        """Fetch detailed task structure including plan and final report."""
        task = await self.repo.get_by_id(task_id)
        if not task:
            return None

        if task.user_id != user_id and user_id != "admin-user":
            return None

        workflow_app = await get_workflow_app()
        state_snapshot = await workflow_app.aget_state({"configurable": {"thread_id": task_id}})
        completed_steps = []
        evidence_count = 0

        if state_snapshot and state_snapshot.values:
            completed_steps = state_snapshot.values.get("completed_step_ids", [])
            evidence_count = len(state_snapshot.values.get("evidence", []))

        return TaskDetailResponse(
            task_id=task.id,
            user_id=task.user_id,
            objective=task.objective,
            status=TaskStatus(task.status),
            current_node=task.current_node,
            plan=task.plan_json,
            completed_steps=completed_steps,
            evidence_count=evidence_count,
            final_report=task.final_report,
            error_summary=task.error_summary,
            created_at=task.created_at,
            updated_at=task.updated_at,
            deadline_at=task.deadline_at
        )

    async def get_task_trace(self, task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full chronological execution trace from checkpoint state."""
        task = await self.repo.get_by_id(task_id)
        if not task or (task.user_id != user_id and user_id != "admin-user"):
            return None

        workflow_app = await get_workflow_app()
        state_snapshot = await workflow_app.aget_state({"configurable": {"thread_id": task_id}})
        trace = []
        if state_snapshot and state_snapshot.values:
            trace = state_snapshot.values.get("execution_trace", [])

        return {
            "task_id": task_id,
            "status": task.status,
            "trace_events": trace
        }
