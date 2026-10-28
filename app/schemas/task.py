"""Pydantic Schemas for Task Ingestion, Status, and Results."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    PAUSED_APPROVAL = "PAUSED_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskCreateRequest(BaseModel):
    objective: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Natural language description of the objective"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional initial parameter payload or constraints"
    )
    max_execution_seconds: Optional[float] = Field(
        default=300.0,
        ge=10.0,
        le=1800.0,
        description="Maximum execution deadline in seconds"
    )


class TaskCreateResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    poll_url: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    current_node: Optional[str] = None
    completed_steps_count: int = 0
    total_steps_count: int = 0
    error_summary: Optional[str] = None
    started_at: datetime
    updated_at: datetime
    deadline_at: datetime


class TaskDetailResponse(BaseModel):
    task_id: str
    user_id: str
    objective: str
    status: TaskStatus
    current_node: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    completed_steps: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    final_report: Optional[str] = None
    error_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deadline_at: datetime


class TaskCancelResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str
