"""Approval Management Service.
Coordinates Human-In-The-Loop approvals, hash verification, and workflow resumption.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ApprovalException, PlatformException, ErrorCategory
from app.core.logging import logger
from app.core.security import compute_operation_hash
from app.graph.workflow import get_workflow_app
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.approval import (
    ApprovalDecision,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalRequestItem,
    ApprovalStatus,
    RiskLevel,
)


class ApprovalService:
    """Manages approval queries, authorization, and workflow resume."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ApprovalRepository(session)
        self.task_repo = TaskRepository(session)

    async def list_pending_approvals(self) -> List[ApprovalRequestItem]:
        """List all approvals currently pending human review."""
        items = await self.repo.list_pending()
        return [
            ApprovalRequestItem(
                approval_id=r.id,
                task_id=r.task_id,
                step_id=r.step_id,
                tool_name=r.tool_name,
                operation_hash=r.operation_hash,
                risk_level=RiskLevel(r.risk_level),
                status=ApprovalStatus(r.status),
                proposed_arguments=r.payload_summary,
                reason_for_approval=r.reason,
                created_at=r.created_at,
                expires_at=r.expires_at
            )
            for r in items
        ]

    async def get_approval(self, approval_id: str) -> Optional[ApprovalRequestItem]:
        """Fetch specific approval item."""
        r = await self.repo.get_by_id(approval_id)
        if not r:
            return None
        return ApprovalRequestItem(
            approval_id=r.id,
            task_id=r.task_id,
            step_id=r.step_id,
            tool_name=r.tool_name,
            operation_hash=r.operation_hash,
            risk_level=RiskLevel(r.risk_level),
            status=ApprovalStatus(r.status),
            proposed_arguments=r.payload_summary,
            reason_for_approval=r.reason,
            created_at=r.created_at,
            expires_at=r.expires_at
        )

    async def submit_decision(
        self,
        approval_id: str,
        request: ApprovalDecisionRequest,
        approver_id: str
    ) -> ApprovalDecisionResponse:
        """Process an approval or rejection decision and resume workflow."""
        r = await self.repo.get_by_id(approval_id)
        if not r:
            raise PlatformException("Approval request not found", category=ErrorCategory.VALIDATION_ERROR)

        if r.status != "PENDING":
            raise PlatformException(
                f"Approval request is already {r.status} and cannot be modified",
                category=ErrorCategory.POLICY_VIOLATION
            )

        # Check expiration (handle SQLite timezone-naive storage)
        now_utc = datetime.now(timezone.utc)
        expires_at_utc = r.expires_at.replace(tzinfo=timezone.utc) if r.expires_at.tzinfo is None else r.expires_at
        if now_utc > expires_at_utc:
            r.status = "EXPIRED"
            await self.session.commit()
            raise ApprovalException("Approval request has expired", is_rejected=True)

        # Record decision in database
        updated = await self.repo.record_decision(
            approval_id=approval_id,
            decision=request.decision.value,
            approver_id=approver_id,
            decision_notes=request.notes
        )

        task_id = r.task_id

        # Resume workflow through LangGraph checkpointer
        import asyncio
        asyncio.create_task(self._resume_workflow_async(task_id, approval_id, request.decision.value, request.notes))

        return ApprovalDecisionResponse(
            approval_id=approval_id,
            task_id=task_id,
            decision=request.decision,
            decided_by=approver_id,
            decided_at=updated.decided_at,
            workflow_resumed=True,
            message=f"Approval decision '{request.decision.value}' recorded. Workflow resumed."
        )

    async def _resume_workflow_async(
        self,
        task_id: str,
        approval_id: str,
        decision: str,
        notes: Optional[str]
    ) -> None:
        """Resume execution of paused LangGraph workflow with updated decision."""
        from app.db.session import AsyncSessionLocal
        from app.graph.workflow import get_workflow_app

        workflow_app = await get_workflow_app()
        config = {"configurable": {"thread_id": task_id}}

        # Update state checkpoint with approval decision
        resume_payload = {
            "status": "RUNNING",
            "pending_approval": None,
            "approval_decision": {
                "approval_id": approval_id,
                "decision": decision,
                "notes": notes
            }
        }

        try:
            # Update state in checkpointer
            await workflow_app.aupdate_state(config, resume_payload)
            # Re-invoke workflow to continue from approval checkpoint
            final_state = await workflow_app.ainvoke(None, config=config)

            # Persist updated status
            async with AsyncSessionLocal() as session:
                task_repo = TaskRepository(session)
                await task_repo.update_task_progress(
                    task_id=task_id,
                    status=final_state.get("status", "COMPLETED"),
                    current_node=final_state.get("current_node"),
                    final_report=final_state.get("final_report"),
                    error_summary=final_state.get("error_summary")
                )
        except Exception as e:
            logger.error(f"Failed to resume workflow {task_id}: {e}", exc_info=True)
