"""Approval Request Repository.
Data access layer for human-in-the-loop approval requests and decisions.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.approval import ApprovalRequest


class ApprovalRepository:
    """Async database operations for approval requests."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, approval_id: str) -> Optional[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> List[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.task_id == task_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending(self) -> List[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.status == "PENDING")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_request(
        self,
        approval_id: str,
        task_id: str,
        step_id: str,
        tool_name: str,
        operation_hash: str,
        payload_summary: Dict[str, Any],
        risk_level: str,
        reason: str,
        expires_at: datetime
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            id=approval_id,
            task_id=task_id,
            step_id=step_id,
            tool_name=tool_name,
            operation_hash=operation_hash,
            payload_summary=payload_summary,
            risk_level=risk_level,
            status="PENDING",
            reason=reason,
            expires_at=expires_at
        )
        self.session.add(req)
        await self.session.flush()
        return req

    async def record_decision(
        self,
        approval_id: str,
        decision: str,
        approver_id: str,
        decision_notes: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        req = await self.get_by_id(approval_id)
        if not req:
            return None

        req.status = decision
        req.approver_id = approver_id
        req.decision_notes = decision_notes
        req.decided_at = datetime.now(timezone.utc)
        await self.session.commit()
        return req
