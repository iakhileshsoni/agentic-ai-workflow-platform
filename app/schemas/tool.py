"""Pydantic Schemas for Tool Metadata, Registration, and Traces."""
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ToolRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ToolMetadataDTO(BaseModel):
    name: str
    description: str
    risk_tier: ToolRisk
    requires_approval: bool
    required_permission: str
    timeout_seconds: float
    max_retries: int
    is_idempotent: bool
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class ToolExecutionTraceItem(BaseModel):
    step_id: str
    tool_name: str
    input_payload: Dict[str, Any]
    output_payload: Optional[Dict[str, Any]] = None
    duration_ms: float
    is_success: bool
    error: Optional[str] = None
