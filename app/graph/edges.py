"""Conditional Graph Transition Edges and Routers for Phase 2.
Directs flow through approval gates, bounded retries, and controlled replanning.
"""
from typing import Literal
from langgraph.graph import END
from app.graph.state import GraphState


def route_after_init(state: GraphState) -> Literal["plan_node", "__end__"]:
    """Route after task initialization."""
    if state.get("status") in ("FAILED", "CANCELLED"):
        return END
    return "plan_node"


def route_after_validation(state: GraphState) -> Literal["select_step_node", "__end__"]:
    """Route after plan validation."""
    if state.get("status") in ("FAILED", "CANCELLED"):
        return END
    return "select_step_node"


def route_after_step_selection(state: GraphState) -> Literal["approval_gate_node", "execute_tool_node", "decide_next_node", "__end__"]:
    """Route after selecting next runnable step."""
    if state.get("status") in ("FAILED", "CANCELLED"):
        return END

    step_id = state.get("current_step_id")
    if not step_id:
        return "decide_next_node"

    step = state.get("steps", {}).get(step_id, {})
    requires_approval = step.get("requires_approval", False)

    # Check if approval decision was already granted for this step
    decision_obj = state.get("approval_decision")
    if requires_approval and not (decision_obj and decision_obj.get("decision") == "APPROVED"):
        return "approval_gate_node"

    return "execute_tool_node"


def route_after_approval_gate(state: GraphState) -> Literal["execute_tool_node", "decide_next_node", "__end__"]:
    """Route after passing through approval gate."""
    status = state.get("status")
    if status in ("PAUSED_APPROVAL", "FAILED", "CANCELLED"):
        return END
    return "execute_tool_node"


def route_after_decision(state: GraphState) -> Literal["select_step_node", "replan_node", "synthesize_report_node", "__end__"]:
    """Route after step verification and decision."""
    status = state.get("status")
    if status in ("FAILED", "CANCELLED"):
        return END
    if status == "REPLANNING":
        return "replan_node"
    if status == "COMPLETED":
        return "synthesize_report_node"
    return "select_step_node"
