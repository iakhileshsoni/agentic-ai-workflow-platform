"""Pydantic Schemas for Structured Planning and Steps.
Defines the strictly bounded output schema expected from the Planner LLM/Mock.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step_id: str = Field(..., description="Unique step identifier, e.g. 'step_1'")
    step_name: str = Field(..., description="Short human-readable title of the step")
    tool_name: str = Field(..., description="Authorized tool identifier from ToolRegistry")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Typed arguments for the tool")
    dependencies: List[str] = Field(default_factory=list, description="List of step_ids that must complete first")
    expected_output: str = Field(..., description="Description of the expected evidence or output")
    requires_approval: bool = Field(default=False, description="Flag indicating if human sign-off is required")


class ExecutionPlan(BaseModel):
    objective: str = Field(..., description="Validated objective of the workflow")
    steps: List[PlanStep] = Field(..., min_length=1, max_length=8, description="Ordered execution steps (max 8)")
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution constraints (timeout, max retries, budget)"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Reasoning behind tool selection and dependency ordering"
    )
