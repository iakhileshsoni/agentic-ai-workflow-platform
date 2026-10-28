"""Integration Test for Human-in-the-Loop Approval Lifecycle.
Verifies workflow pause on sensitive tool, state persistence in SQLite checkpointer,
and resumption upon approval decision.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.approvals.service import ApprovalService
from app.db.session import AsyncSessionLocal
from app.graph.workflow import get_workflow_app
from app.schemas.approval import ApprovalDecision, ApprovalDecisionRequest
from app.schemas.plan import ExecutionPlan, PlanStep


@pytest.mark.asyncio
async def test_human_approval_pause_and_resume():
    task_id = str(uuid.uuid4())
    user_id = "test-operator-01"
    objective = "Research vector databases and publish the executive summary to Slack"
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)

    # Initial state with a step requiring approval
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
                    "step_name": "Export Report to Slack",
                    "tool_name": "sensitive_export_action",
                    "arguments": {
                        "action_type": "publish_report",
                        "target_destination": "slack://#executive-briefs",
                        "payload_summary": "Top 3 Vector Databases Comparison"
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
                "step_name": "Export Report to Slack",
                "tool_name": "sensitive_export_action",
                "arguments": {
                    "action_type": "publish_report",
                    "target_destination": "slack://#executive-briefs",
                    "payload_summary": "Top 3 Vector Databases Comparison"
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

    # 1. Execute workflow: should pause at approval_gate_node
    paused_state = await workflow_app.ainvoke(initial_state, config=config)
    assert paused_state["status"] == "PAUSED_APPROVAL"

    # Verify checkpointer recorded paused state
    snapshot = await workflow_app.aget_state(config)
    assert snapshot.values["status"] == "PAUSED_APPROVAL"

    # 2. Check pending approvals via ApprovalService
    async with AsyncSessionLocal() as session:
        service = ApprovalService(session)
        pending = await service.list_pending_approvals()
        matching = [p for p in pending if p.task_id == task_id]
        assert len(matching) == 1
        approval_id = matching[0].approval_id
        assert matching[0].tool_name == "sensitive_export_action"

        # 3. Submit APPROVED decision
        decision_req = ApprovalDecisionRequest(
            decision=ApprovalDecision.APPROVED,
            notes="Sign-off granted for executive summary broadcast."
        )
        res = await service.submit_decision(
            approval_id=approval_id,
            request=decision_req,
            approver_id="admin-user"
        )
        assert res.workflow_resumed is True

    # Allow background resume task to execute
    import asyncio
    await asyncio.sleep(0.5)

    # 4. Check resumed state from checkpointer
    resumed_snapshot = await workflow_app.aget_state(config)
    assert resumed_snapshot.values["status"] == "COMPLETED"
    assert "step_1" in resumed_snapshot.values["completed_step_ids"]
    assert resumed_snapshot.values["step_outputs"]["step_1"]["is_executed"] is True
