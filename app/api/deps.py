"""API Dependencies Injection Module."""
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_api_key
from app.db.session import get_db_session
from app.services.task_service import TaskService


async def get_task_service(
    session: AsyncSession = Depends(get_db_session),
) -> TaskService:
    """Provide initialized TaskService instance."""
    return TaskService(session)
