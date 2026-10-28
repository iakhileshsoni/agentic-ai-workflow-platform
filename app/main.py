"""FastAPI Main Application Entry Point.
Configures lifespan, middleware, routers, and global exception handlers.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import PlatformException
from app.core.logging import logger
from app.db.session import init_db
from app.graph.checkpointer import async_checkpointer_manager
from app.graph.workflow import get_workflow_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle events."""
    logger.info("Initializing Agentic AI Workflow Platform...")
    settings.ensure_directories()
    # Initialize application SQLite database tables
    await init_db()
    # Initialize LangGraph Async SQLite checkpointer and compile workflow
    await get_workflow_app()
    logger.info("Platform initialized and ready for execution.")
    yield
    logger.info("Shutting down platform...")
    await async_checkpointer_manager.close()


app = FastAPI(
    title=settings.APP_NAME,
    description="Stateful Multi-Step Agentic Workflow Automation Platform with LangGraph Orchestration",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 API router
app.include_router(api_v1_router)


@app.exception_handler(PlatformException)
async def platform_exception_handler(request: Request, exc: PlatformException):
    """Uniform JSON response handler for platform domain exceptions."""
    logger.warning(f"Domain exception on {request.url.path}: {exc.message} ({exc.category})")
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.category.value == "POLICY_VIOLATION":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.category.value == "AUTHORIZATION_FAILURE":
        status_code = status.HTTP_401_UNAUTHORIZED

    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.APP_DEBUG)
