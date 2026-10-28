"""Workflow Graph Construction and Compiler for Phase 2.
Builds the LangGraph state machine with persistent AsyncSqliteSaver checkpointer,
approval gate node, and replan node.
"""
from typing import Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from app.graph.checkpointer import async_checkpointer_manager
from app.graph.edges import (
    route_after_init,
    route_after_validation,
    route_after_step_selection,
    route_after_approval_gate,
    route_after_decision,
)
from app.graph.nodes import (
    init_task_node,
    plan_node,
    validate_plan_node,
    select_step_node,
    approval_gate_node,
    execute_tool_node,
    verify_result_node,
    replan_node,
    decide_next_node,
    synthesize_report_node,
)
from app.graph.state import GraphState


def create_state_graph() -> StateGraph:
    """Construct StateGraph and wire nodes and conditional transitions."""
    workflow = StateGraph(GraphState)

    # Add execution nodes
    workflow.add_node("init_task_node", init_task_node)
    workflow.add_node("plan_node", plan_node)
    workflow.add_node("validate_plan_node", validate_plan_node)
    workflow.add_node("select_step_node", select_step_node)
    workflow.add_node("approval_gate_node", approval_gate_node)
    workflow.add_node("execute_tool_node", execute_tool_node)
    workflow.add_node("verify_result_node", verify_result_node)
    workflow.add_node("replan_node", replan_node)
    workflow.add_node("decide_next_node", decide_next_node)
    workflow.add_node("synthesize_report_node", synthesize_report_node)

    # Wire edges
    workflow.add_edge(START, "init_task_node")
    workflow.add_conditional_edges(
        "init_task_node",
        route_after_init,
        {
            "plan_node": "plan_node",
            END: END
        }
    )
    workflow.add_edge("plan_node", "validate_plan_node")

    # Conditional routing after validation
    workflow.add_conditional_edges(
        "validate_plan_node",
        route_after_validation,
        {
            "select_step_node": "select_step_node",
            END: END
        }
    )

    # Conditional routing after selecting step
    workflow.add_conditional_edges(
        "select_step_node",
        route_after_step_selection,
        {
            "approval_gate_node": "approval_gate_node",
            "execute_tool_node": "execute_tool_node",
            "decide_next_node": "decide_next_node",
            END: END
        }
    )

    # Conditional routing after approval gate
    workflow.add_conditional_edges(
        "approval_gate_node",
        route_after_approval_gate,
        {
            "execute_tool_node": "execute_tool_node",
            "decide_next_node": "decide_next_node",
            END: END
        }
    )

    # Step execution pipeline
    workflow.add_edge("execute_tool_node", "verify_result_node")
    workflow.add_edge("verify_result_node", "decide_next_node")

    # Edge after replanning
    workflow.add_edge("replan_node", "select_step_node")

    # Conditional routing after decision
    workflow.add_conditional_edges(
        "decide_next_node",
        route_after_decision,
        {
            "select_step_node": "select_step_node",
            "replan_node": "replan_node",
            "synthesize_report_node": "synthesize_report_node",
            END: END
        }
    )

    workflow.add_edge("synthesize_report_node", END)
    return workflow


_compiled_app: Optional[CompiledStateGraph] = None


async def get_workflow_app() -> CompiledStateGraph:
    """Retrieve or compile the LangGraph workflow with AsyncSqliteSaver."""
    global _compiled_app
    if _compiled_app is None:
        saver = await async_checkpointer_manager.get_saver()
        graph = create_state_graph()
        _compiled_app = graph.compile(checkpointer=saver)
    return _compiled_app
