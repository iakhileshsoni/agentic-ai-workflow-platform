"""Report and Evidence Retrieval API Endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from app.api.deps import get_task_service
from app.core.security import verify_api_key
from app.services.task_service import TaskService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/{task_id}/markdown",
    response_class=PlainTextResponse,
    summary="Download final report as formatted Markdown text"
)
async def get_report_markdown(
    task_id: str,
    user_id: str = Depends(verify_api_key),
    service: TaskService = Depends(get_task_service)
):
    """Retrieve raw Markdown content of the completed report."""
    detail = await service.get_task_detail(task_id, user_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or access denied")
    if not detail.final_report:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task report is not yet synthesized")
    return detail.final_report
