"""Simulated Sensitive Action Tool.
Demonstrates Human-In-The-Loop approval gates safely without external side effects.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, RiskTier, ToolPermission


class SensitiveActionInput(BaseModel):
    action_type: str = Field(..., description="Action to perform: 'publish_report', 'export_dataset', or 'notify_stakeholders'")
    target_destination: str = Field(..., description="Destination target, e.g. 's3://production-reports', 'slack://#exec-briefs'")
    payload_summary: str = Field(..., description="Executive summary or payload identifier to export")


class SensitiveActionOutput(BaseModel):
    action_id: str
    action_type: str
    target_destination: str
    is_executed: bool
    confirmation_message: str


class SensitiveActionTool(BaseTool):
    name = "sensitive_export_action"
    description = "Export or publish research findings to an external destination. Requires explicit human sign-off."
    input_schema = SensitiveActionInput
    output_schema = SensitiveActionOutput
    risk_tier = RiskTier.CRITICAL
    requires_approval = True
    required_permission = ToolPermission.ADMIN
    timeout_seconds = 10.0
    max_retries = 1
    is_idempotent = True

    async def execute(self, arguments: SensitiveActionInput, context: Optional[Dict[str, Any]] = None) -> SensitiveActionOutput:
        import uuid
        action_id = f"act-{uuid.uuid4().hex[:8]}"
        msg = f"Action '{arguments.action_type}' safely dispatched to destination '{arguments.target_destination}'."

        return SensitiveActionOutput(
            action_id=action_id,
            action_type=arguments.action_type,
            target_destination=arguments.target_destination,
            is_executed=True,
            confirmation_message=msg
        )
