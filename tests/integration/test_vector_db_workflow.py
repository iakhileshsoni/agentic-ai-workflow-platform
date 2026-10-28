"""Integration Test for End-to-End Vector Database Research Workflow.
Tests the full LangGraph state machine execution, tool chain, and checkpointing.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.graph.workflow import get_workflow_app


@pytest.mark.asyncio
async def test_vector_db_research_workflow_end_to_end():
    task_id = str(uuid.uuid4())
    user_id = "test-engineer-01"
    objective = (
        "Research three candidate vector databases using approved information sources, "
        "compare their supported capabilities and pricing information where available, "
        "identify important trade-offs, and prepare a recommendation report."
    )
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)

    initial_state = {
        "task_id": task_id,
        "user_id": user_id,
        "objective": objective,
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
        "max_steps": 8,
        "max_replans": 2,
        "deadline_at": deadline.isoformat(),
        "final_report": None,
        "error_summary": None,
        "execution_trace": []
    }

    config = {"configurable": {"thread_id": task_id}}

    workflow_app = await get_workflow_app()
    # Execute workflow graph
    final_state = await workflow_app.ainvoke(initial_state, config=config)

    # Assertions
    assert final_state["status"] == "COMPLETED"
    assert len(final_state["completed_step_ids"]) >= 5
    assert len(final_state["failed_step_ids"]) == 0
    assert final_state["final_report"] is not None
    assert "Vector Database Research & Comparative Recommendation Report" in final_state["final_report"]
    assert "Qdrant" in final_state["final_report"]
    assert "Milvus" in final_state["final_report"]
    assert "Pinecone" in final_state["final_report"]

    # Verify checkpointer persistence: state snapshot can be retrieved
    snapshot = await workflow_app.aget_state(config)
    assert snapshot is not None
    assert snapshot.values["task_id"] == task_id
    assert snapshot.values["status"] == "COMPLETED"
