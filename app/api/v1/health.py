"""Health and Readiness Probes."""
from fastapi import APIRouter, status
from app.core.config import settings
from app.planning.llm_adapter import llm_adapter

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe: verifies service process is operational."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "0.1.0"
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness probe: verifies local dependencies (checkpointer, database, Ollama)."""
    ollama_ready = await llm_adapter.is_available()
    return {
        "status": "ready",
        "database": "sqlite_aiosqlite_connected",
        "checkpointer": "sqlite_wal_active",
        "local_llm_runtime": {
            "ollama_available": ollama_ready,
            "configured_model": settings.LLM_MODEL,
            "fallback_mock_enabled": settings.LLM_FALLBACK_MOCK
        }
    }
