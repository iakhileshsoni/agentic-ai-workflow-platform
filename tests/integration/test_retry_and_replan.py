"""Integration Test for Bounded Retries and Controlled Replanning."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import pytest
from app.graph.workflow import get_workflow_app
from app.tools.base import BaseTool, RiskTier, ToolPermission
from app.tools.registry import tool_registry


class FlakyInput(BaseModel):
    fail_until_attempt: int = Field(default=2)


class FlakyOutput(BaseModel):
    success: bool
    attempt_number: int


class FlakyTool(BaseTool):
    name = "flaky_mock_tool"
    description = "Fails transiently until specified attempt count."
    input_schema = FlakyInput
    output_schema = FlakyOutput
    risk_tier = RiskTier.LOW
    requires_approval = False
    required_permission = ToolPermission.READ
    timeout_seconds = 5.0
    max_retries = 2
    is_idempotent = True

    def __init__(self):
        self.call_count = 0

    async def execute(self, arguments: FlakyInput, context: Optional[Dict[str, Any]] = None) -> FlakyOutput:
        self.call_count += 1
        if self.call_count < arguments.fail_until_attempt:
            raise RuntimeError(f"Simulated transient error on attempt {self.call_count}")
        return FlakyOutput(success=True, attempt_number=self.call_count)


@pytest.mark.asyncio
async def test_transient_tool_failure_retry_success():
    flaky = FlakyTool()
    tool_registry.register(flaky)

    task_id = str(uuid.uuid4())
    user_id = "test-reliability"
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)

    initial_state = {
        "task_id": task_id,
        "user_id": user_id,
        "objective": "Test retry on transient tool failure",
        "status": "SUBMITTED",
        "current_node": "init_task_node",
        "current_step_id": None,
        "plan": {
            "objective": "Test retry",
            "steps": [
                {
                    "step_id": "step_1",
                    "step_name": "Call Flaky Tool",
                    "tool_name": "flaky_mock_tool",
                    "arguments": {"fail_until_attempt": 2},
                    "dependencies": [],
                    "expected_output": "Success on retry",
                    "requires_approval": False
                }
            ],
            "constraints": {"max_steps": 1}
        },
        "steps": {
            "step_1": {
                "step_id": "step_1",
                "step_name": "Call Flaky Tool",
                "tool_name": "flaky_mock_tool",
                "arguments": {"fail_until_attempt": 2},
                "dependencies": [],
                "expected_output": "Success on retry",
                "status": "PENDING",
                "result": None,
                "error": None,
                "retry_count": 0,
                "requires_approval": False,
                "approval_id": None
            }
        },
        "completed_step_ids": [],
        "failed_step_ids": [],
        "step_outputs": {},
        "evidence": [],
        "step_counter": 0,
        "replan_counter": 0,
        "model_call_counter": 0,
        "max_steps": 5,
        "max_replans": 2,
        "deadline_at": deadline.isoformat(),
        "is_cancelled": False,
        "pending_approval": None,
        "approval_decision": None,
        "final_report": None,
        "error_summary": None,
        "execution_trace": []
    }

    config = {"configurable": {"thread_id": task_id}}
    workflow_app = await get_workflow_app()

    final_state = await workflow_app.ainvoke(initial_state, config=config)

    # Tool failed on attempt 1, retried, and succeeded on attempt 2
    assert final_state["status"] == "COMPLETED"
    assert "step_1" in final_state["completed_step_ids"]
    assert flaky.call_count == 2
