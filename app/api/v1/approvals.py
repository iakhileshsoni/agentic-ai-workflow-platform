"""Human-in-the-Loop Approval API Endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.approvals.service import ApprovalService
from app.core.security import verify_api_key
from app.db.session import get_db_session
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalRequestItem,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def get_approval_service(session: AsyncSession = Depends(get_db_session)) -> ApprovalService:
    return ApprovalService(session)


@router.get(
    "",
    response_model=List[ApprovalRequestItem],
    summary="List pending approval requests requiring human decision"
)
async def list_pending_approvals(
    user_id: str = Depends(verify_api_key),
    service: ApprovalService = Depends(get_approval_service)
):
    """Retrieve all pending approval requests awaiting operator sign-off."""
    return await service.list_pending_approvals()


@router.get(
    "/{approval_id}",
    response_model=ApprovalRequestItem,
    summary="Get details of a specific approval request"
)
async def get_approval_item(
    approval_id: str,
    user_id: str = Depends(verify_api_key),
    service: ApprovalService = Depends(get_approval_service)
):
    """Inspect arguments, tool name, risk level, and operation hash for an approval."""
    res = await service.get_approval(approval_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return res


@router.post(
    "/{approval_id}/decision",
    response_model=ApprovalDecisionResponse,
    summary="Submit an approval or rejection decision"
)
async def submit_approval_decision(
    approval_id: str,
    request: ApprovalDecisionRequest,
    user_id: str = Depends(verify_api_key),
    service: ApprovalService = Depends(get_approval_service)
):
    """Decide an approval request (APPROVED or REJECTED) and resume the paused LangGraph workflow."""
    return await service.submit_decision(
        approval_id=approval_id,
        request=request,
        approver_id=user_id
    )
