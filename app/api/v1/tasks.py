"""Task Management API Endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.api.deps import get_task_service
from app.core.security import verify_api_key
from app.schemas.task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatusResponse,
    TaskDetailResponse,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskCreateResponse,
    summary="Submit a new multi-step agent workflow task"
)
async def create_task(
    request: TaskCreateRequest,
    user_id: str = Depends(verify_api_key),
    service: TaskService = Depends(get_task_service),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """Ingests a natural language user objective, validates parameters, and dispatches the execution graph."""
    return await service.submit_task(
        request=request,
        user_id=user_id,
        idempotency_key=idempotency_key
    )


@router.get(
    "/{task_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=TaskStatusResponse,
    summary="Poll task execution status and progress"
)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(verify_api_key),
    service: TaskService = Depends(get_task_service)
):
    """Retrieve current task status, active node, and completed step count."""
    res = await service.get_task_status(task_id, user_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or access denied")
    return res


@router.get(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    response_model=TaskDetailResponse,
    summary="Get comprehensive task details, plan, and final report"
)
async def get_task_detail(
    task_id: str,
    user_id: str = Depends(verify_api_key),
    service: TaskService = Depends(get_task_service)
):
    """Retrieve complete task record, including validated plan, completed step IDs, and report."""
    res = await service.get_task_detail(task_id, user_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or access denied")
    return res


@router.get(
    "/{task_id}/trace",
    status_code=status.HTTP_200_OK,
    summary="Get full chronological execution trace"
)
async def get_task_trace(
    task_id: str,
    user_id: str = Depends(verify_api_key),
    service: TaskService = Depends(get_task_service)
):
    """Retrieve detailed node transitions, tool invocations, and timing metrics."""
    res = await service.get_task_trace(task_id, user_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or access denied")
    return res
