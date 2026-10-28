"""V1 Aggregate Router."""
from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.reports import router as reports_router
from app.api.v1.approvals import router as approvals_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(approvals_router)
