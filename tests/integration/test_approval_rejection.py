"""Integration Test for Approval Rejection Behavior."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.approvals.service import ApprovalService
from app.db.session import AsyncSessionLocal
from app.graph.workflow import get_workflow_app
from app.schemas.approval import ApprovalDecision, ApprovalDecisionRequest


@pytest.mark.asyncio
async def test_human_approval_rejection_leads_to_safe_failure():
    task_id = str(uuid.uuid4())
    user_id = "test-operator-02"
    objective = "Export unauthorized dataset"
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)

    initial_state = {
        "task_id": task_id,
        "user_id": user_id,
        "objective": objective,
        "status": "SUBMITTED",
        "current_node": "init_task_node",
        "current_step_id": None,
        "plan": {
            "objective": objective,
            "steps": [
                {
                    "step_id": "step_1",
                    "step_name": "Export Data",
                    "tool_name": "sensitive_export_action",
                    "arguments": {
                        "action_type": "export_dataset",
                        "target_destination": "s3://unauthorized-bucket",
                        "payload_summary": "Customer PII"
                    },
                    "dependencies": [],
                    "expected_output": "Export confirmation",
                    "requires_approval": True
                }
            ],
            "constraints": {"max_steps": 1}
        },
        "steps": {
            "step_1": {
                "step_id": "step_1",
                "step_name": "Export Data",
                "tool_name": "sensitive_export_action",
                "arguments": {
                    "action_type": "export_dataset",
                    "target_destination": "s3://unauthorized-bucket",
                    "payload_summary": "Customer PII"
                },
                "dependencies": [],
                "expected_output": "Export confirmation",
                "status": "PENDING",
                "result": None,
                "error": None,
                "retry_count": 0,
                "requires_approval": True,
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
        "max_replans": 0,  # No replans allowed
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

    # 1. Execute until paused
    paused_state = await workflow_app.ainvoke(initial_state, config=config)
    assert paused_state["status"] == "PAUSED_APPROVAL"

    # 2. Reject request
    async with AsyncSessionLocal() as session:
        service = ApprovalService(session)
        pending = await service.list_pending_approvals()
        matching = [p for p in pending if p.task_id == task_id]
        assert len(matching) == 1
        approval_id = matching[0].approval_id

        decision_req = ApprovalDecisionRequest(
            decision=ApprovalDecision.REJECTED,
            notes="Rejected: Destination bucket is not compliant with policy."
        )
        await service.submit_decision(
            approval_id=approval_id,
            request=decision_req,
            approver_id="security-officer"
        )

    await asyncio.sleep(0.5)

    # 3. Verify terminal failure
    snapshot = await workflow_app.aget_state(config)
    assert snapshot.values["status"] == "FAILED"
    assert "rejected" in snapshot.values["error_summary"].lower()
