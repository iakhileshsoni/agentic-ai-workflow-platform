"""Pydantic Schemas for Human-in-the-Loop Approval Requests and Decisions."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequestItem(BaseModel):
    approval_id: str
    task_id: str
    step_id: str
    tool_name: str
    operation_hash: str
    risk_level: RiskLevel
    status: ApprovalStatus
    proposed_arguments: Dict[str, Any]
    reason_for_approval: str
    created_at: datetime
    expires_at: datetime


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    notes: Optional[str] = Field(default=None, max_length=500, description="Approver justification notes")


class ApprovalDecisionResponse(BaseModel):
    approval_id: str
    task_id: str
    decision: ApprovalDecision
    decided_by: str
    decided_at: datetime
    workflow_resumed: bool
    message: str
