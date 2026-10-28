"""LangGraph Execution State Schema.
Explicit, typed dictionary storing workflow context, steps, evidence, and traces.
"""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class StepState(TypedDict):
    step_id: str
    step_name: str
    tool_name: str
    arguments: Dict[str, Any]
    dependencies: List[str]
    expected_output: str
    status: str                         # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    requires_approval: bool
    approval_id: Optional[str]


class GraphState(TypedDict):
    # Context & Identifiers
    task_id: str
    user_id: str
    objective: str
    status: str                         # SUBMITTED, PLANNING, RUNNING, PAUSED_APPROVAL, COMPLETED, FAILED, CANCELLED
    
    # Navigation
    current_node: str
    current_step_id: Optional[str]
    
    # Plan & Execution Steps
    plan: Optional[Dict[str, Any]]
    steps: Dict[str, StepState]
    completed_step_ids: List[str]
    failed_step_ids: List[str]
    
    # Intermediate Outputs & Verified Evidence Bank
    step_outputs: Dict[str, Any]        # step_id -> result payload
    evidence: List[Dict[str, Any]]      # Verified claims / outputs
    
    # Resource Bounds and Counters
    step_counter: int
    replan_counter: int
    model_call_counter: int
    max_steps: int
    max_replans: int
    deadline_at: str                    # ISO-8601 UTC string
    is_cancelled: bool                  # Cooperative cancellation flag

    # Human-In-The-Loop Approval Data
    pending_approval: Optional[Dict[str, Any]]
    approval_decision: Optional[Dict[str, Any]] # {"approval_id": ..., "decision": "APPROVED"|"REJECTED", "notes": ...}
    final_report: Optional[str]
    error_summary: Optional[str]
    execution_trace: List[Dict[str, Any]]
