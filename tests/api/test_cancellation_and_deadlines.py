"""API and State Tests for Cancellation and Deadlines."""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.graph.workflow import get_workflow_app


@pytest.mark.asyncio
async def test_task_cancellation_api(async_client: AsyncClient):
    payload = {
        "objective": "Long running simulation task to be cancelled",
        "parameters": {}
    }
    headers = {"X-API-Key": "test-admin"}

    res = await async_client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 202
    task_id = res.json()["task_id"]

    # Cancel task
    cancel_res = await async_client.post(f"/api/v1/tasks/{task_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_task_deadline_expiration_fails_gracefully():
    task_id = str(uuid.uuid4())
    # Deadline already in past (10 seconds ago)
    past_deadline = datetime.now(timezone.utc) - timedelta(seconds=10)

    initial_state = {
        "task_id": task_id,
        "user_id": "test-user",
        "objective": "Expired deadline task",
        "status": "SUBMITTED",
        "current_node": "init_task_node",
        "current_step_id": None,
        "plan": None,
        "steps": {},
        "completed_step_ids": [],
        "failed_step_ids": [],
        "step_outputs": {},
        "evidence": [],
        "step_counter": 0,
        "replan_counter": 0,
        "model_call_counter": 0,
        "max_steps": 5,
        "max_replans": 2,
        "deadline_at": past_deadline.isoformat(),
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

    assert final_state["status"] == "FAILED"
    assert "deadline exceeded" in final_state["error_summary"].lower()
