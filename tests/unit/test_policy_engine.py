"""Unit Tests for Policy and Plan Validation Engine."""
import pytest
from app.core.exceptions import PolicyViolationException
from app.policies.plan_policy import PlanPolicyEngine
from app.schemas.plan import ExecutionPlan, PlanStep


def test_valid_plan_passes():
    engine = PlanPolicyEngine(max_steps=5)
    plan = ExecutionPlan(
        objective="Test calculation",
        steps=[
            PlanStep(
                step_id="step_1",
                step_name="Math",
                tool_name="calculator",
                arguments={"operation": "add", "a": 1, "b": 2},
                dependencies=[],
                expected_output="Sum result"
            )
        ]
    )
    # Should not raise
    engine.validate_plan(plan)


def test_budget_exceeded_raises_policy_violation():
    engine = PlanPolicyEngine(max_steps=2)
    plan = ExecutionPlan(
        objective="Oversized plan",
        steps=[
            PlanStep(step_id=f"step_{i}", step_name="Math", tool_name="calculator", arguments={"operation": "add", "a": 1, "b": 1}, dependencies=[], expected_output="Res")
            for i in range(1, 4)
        ]
    )
    with pytest.raises(PolicyViolationException) as exc_info:
        engine.validate_plan(plan)
    assert "exceeds configured maximum budget" in exc_info.value.message


def test_unauthorized_tool_rejected():
    engine = PlanPolicyEngine()
    plan = ExecutionPlan(
        objective="Illegal tool attempt",
        steps=[
            PlanStep(
                step_id="step_1",
                step_name="Shell Exec",
                tool_name="arbitrary_bash_executor",
                arguments={},
                dependencies=[],
                expected_output="Pwned"
            )
        ]
    )
    with pytest.raises(PolicyViolationException) as exc_info:
        engine.validate_plan(plan)
    assert "unauthorized or nonexistent tool" in exc_info.value.message


def test_circular_dependency_detected():
    engine = PlanPolicyEngine()
    plan = ExecutionPlan(
        objective="Circular plan",
        steps=[
            PlanStep(
                step_id="step_1",
                step_name="Step 1",
                tool_name="calculator",
                arguments={"operation": "add", "a": 1, "b": 1},
                dependencies=["step_2"],  # Depends on step_2
                expected_output="Res 1"
            ),
            PlanStep(
                step_id="step_2",
                step_name="Step 2",
                tool_name="calculator",
                arguments={"operation": "add", "a": 2, "b": 2},
                dependencies=["step_1"],  # Depends on step_1 -> Cycle!
                expected_output="Res 2"
            )
        ]
    )
    with pytest.raises(PolicyViolationException) as exc_info:
        engine.validate_plan(plan)
    assert "Circular dependency cycle detected" in exc_info.value.message
