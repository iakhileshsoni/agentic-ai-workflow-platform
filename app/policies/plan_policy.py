"""Deterministic Plan Policy and Verification Engine.
Enforces non-LLM security rules, tool validation, and budget constraints.
"""
from typing import Dict, List, Set
from pydantic import ValidationError
from app.core.config import settings
from app.core.exceptions import PolicyViolationException
from app.schemas.plan import ExecutionPlan, PlanStep
from app.tools.registry import tool_registry


class PlanPolicyEngine:
    """Enforces application-level policy checks on plans produced by the Planner."""

    def __init__(self, max_steps: int = settings.MAX_PLAN_STEPS):
        self.max_steps = max_steps

    def validate_plan(self, plan: ExecutionPlan) -> None:
        """Run all deterministic policy validations on an incoming plan.
        Raises PolicyViolationException if any check fails.
        """
        self._check_step_budget(plan)
        self._check_tool_authorization(plan)
        self._check_dependency_graph(plan)
        self._check_argument_schemas(plan)

    def _check_step_budget(self, plan: ExecutionPlan) -> None:
        """Ensure plan length does not exceed maximum allowable steps."""
        if len(plan.steps) > self.max_steps:
            raise PolicyViolationException(
                f"Plan step count ({len(plan.steps)}) exceeds configured maximum budget of {self.max_steps} steps",
                details={"step_count": len(plan.steps), "max_allowed": self.max_steps}
            )

    def _check_tool_authorization(self, plan: ExecutionPlan) -> None:
        """Verify that every requested tool exists in the tool registry."""
        for step in plan.steps:
            if not tool_registry.has_tool(step.tool_name):
                raise PolicyViolationException(
                    f"Plan step '{step.step_id}' references unauthorized or nonexistent tool: '{step.tool_name}'",
                    details={"step_id": step.step_id, "tool_name": step.tool_name}
                )

    def _check_dependency_graph(self, plan: ExecutionPlan) -> None:
        """Verify that step dependencies form a valid Directed Acyclic Graph (DAG) without circularities."""
        defined_ids: Set[str] = set()
        step_map: Dict[str, PlanStep] = {}

        for step in plan.steps:
            if step.step_id in defined_ids:
                raise PolicyViolationException(
                    f"Duplicate step ID detected: '{step.step_id}'",
                    details={"step_id": step.step_id}
                )
            defined_ids.add(step.step_id)
            step_map[step.step_id] = step

        # Check dependencies reference only defined steps
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in defined_ids:
                    raise PolicyViolationException(
                        f"Step '{step.step_id}' has dependency on undefined step '{dep}'",
                        details={"step_id": step.step_id, "missing_dep": dep}
                    )
                if dep == step.step_id:
                    raise PolicyViolationException(
                        f"Step '{step.step_id}' cannot depend on itself (circular reference)",
                        details={"step_id": step.step_id}
                    )

        # Detect circular dependencies using DFS cycle detection
        visited: Dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited

        def has_cycle(s_id: str) -> bool:
            visited[s_id] = 1
            for d in step_map[s_id].dependencies:
                if visited.get(d, 0) == 1:
                    return True
                if visited.get(d, 0) == 0 and has_cycle(d):
                    return True
            visited[s_id] = 2
            return False

        for step_id in defined_ids:
            if visited.get(step_id, 0) == 0:
                if has_cycle(step_id):
                    raise PolicyViolationException(
                        f"Circular dependency cycle detected in plan involving step '{step_id}'",
                        details={"cyclic_step": step_id}
                    )

    def _check_argument_schemas(self, plan: ExecutionPlan) -> None:
        """Validate that proposed arguments structurally match each tool's Pydantic schema."""
        for step in plan.steps:
            tool = tool_registry.get_tool(step.tool_name)
            # If arguments are literal dictionary, attempt Pydantic parse
            if step.arguments:
                try:
                    tool.input_schema.model_validate(step.arguments)
                except ValidationError as e:
                    # If arguments contain placeholder templates (e.g. {{step_1.result}}), allow them
                    args_str = str(step.arguments)
                    if "{{" in args_str and "}}" in args_str:
                        continue
                    raise PolicyViolationException(
                        f"Invalid arguments for tool '{step.tool_name}' in step '{step.step_id}': {e.errors()}",
                        details={"step_id": step.step_id, "tool_name": step.tool_name, "validation_errors": e.errors()}
                    )


plan_policy_engine = PlanPolicyEngine()
