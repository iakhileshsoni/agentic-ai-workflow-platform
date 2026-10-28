"""Conditional Graph Transition Edges and Routers.
Ensures deterministic progression and prevents uncontrolled or infinite loops.
"""
from typing import Literal
from langgraph.graph import END
from app.graph.state import GraphState


def route_after_validation(state: GraphState) -> Literal["select_step_node", "__end__"]:
    """Route after plan validation."""
    if state.get("status") == "FAILED":
        return END
    return "select_step_node"


def route_after_step_selection(state: GraphState) -> Literal["execute_tool_node", "decide_next_node"]:
    """Route after selecting next runnable step."""
    if state.get("current_step_id"):
        return "execute_tool_node"
    return "decide_next_node"


def route_after_decision(state: GraphState) -> Literal["select_step_node", "synthesize_report_node", "__end__"]:
    """Route after step verification and decision."""
    status = state.get("status")
    if status == "FAILED":
        return END
    if status == "COMPLETED":
        return "synthesize_report_node"
    return "select_step_node"
