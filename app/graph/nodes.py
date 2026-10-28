"""LangGraph Execution Nodes for Phase 2.
Implements bounded retries, exponential backoff, deadline enforcement,
Human-in-the-Loop approval gates, and controlled replanning.
"""
import copy
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from langgraph.types import interrupt
from app.core.config import settings
from app.core.exceptions import PolicyViolationException, ToolExecutionException
from app.core.logging import logger
from app.core.security import compute_operation_hash
from app.graph.state import GraphState, StepState
from app.planning.planner import planner_service
from app.policies.plan_policy import plan_policy_engine
from app.schemas.plan import ExecutionPlan
from app.tools.registry import tool_registry


def _is_deadline_exceeded(state: GraphState) -> bool:
    """Check if current UTC time has passed the task deadline."""
    deadline_str = state.get("deadline_at")
    if not deadline_str:
        return False
    try:
        deadline = datetime.fromisoformat(deadline_str)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > deadline
    except Exception:
        return False


def _resolve_template_references(args: Any, step_outputs: Dict[str, Any]) -> Any:
    """Recursively resolve placeholder references like {{step_1.databases}} in arguments."""
    if isinstance(args, str):
        pattern = r"^{{\s*([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?\s*}}$"
        match = re.match(pattern, args.strip())
        if match:
            step_ref = match.group(1)
            field_ref = match.group(2)
            if step_ref == "all_outputs":
                return step_outputs
            if step_ref in step_outputs:
                step_data = step_outputs[step_ref]
                if field_ref:
                    if isinstance(step_data, dict):
                        return step_data.get(field_ref, None)
                    return getattr(step_data, field_ref, None)
                return step_data

        def replace_fn(m):
            s_ref = m.group(1)
            f_ref = m.group(2)
            if s_ref in step_outputs:
                val = step_outputs[s_ref]
                if f_ref and isinstance(val, dict):
                    return str(val.get(f_ref, ""))
                return str(val)
            return m.group(0)

        return re.sub(r"{{\s*([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?\s*}}", replace_fn, args)

    if isinstance(args, dict):
        return {k: _resolve_template_references(v, step_outputs) for k, v in args.items()}
    if isinstance(args, list):
        return [_resolve_template_references(item, step_outputs) for item in args]
    return args


async def init_task_node(state: GraphState) -> Dict[str, Any]:
    """Initialize task execution metadata, resource counters, and status."""
    logger.info(f"Initializing task {state['task_id']}")

    if _is_deadline_exceeded(state):
        return {
            "status": "FAILED",
            "current_node": "init_task_node",
            "error_summary": "Task deadline exceeded before initialization"
        }

    if state.get("is_cancelled"):
        return {
            "status": "CANCELLED",
            "current_node": "init_task_node",
            "error_summary": "Task cancelled before initialization"
        }

    return {
        "status": "PLANNING",
        "current_node": "init_task_node",
        "completed_step_ids": [],
        "failed_step_ids": [],
        "step_outputs": {},
        "evidence": [],
        "step_counter": 0,
        "replan_counter": 0,
        "model_call_counter": 0,
        "is_cancelled": False,
        "pending_approval": None,
        "approval_decision": None,
        "execution_trace": [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "init_task_node",
            "event": "Workflow initialized"
        }]
    }


async def plan_node(state: GraphState) -> Dict[str, Any]:
    """Generate structured plan using Planner Service."""
    if state.get("status") in ("FAILED", "CANCELLED") or _is_deadline_exceeded(state):
        return {
            "status": "FAILED",
            "current_node": "plan_node",
            "error_summary": "Task deadline exceeded before planning"
        }

    # If plan and steps were already pre-seeded in state, preserve them!
    if state.get("plan") and state.get("steps"):
        logger.info(f"Using pre-configured plan for task {state['task_id']}")
        return {
            "status": "PLANNING",
            "current_node": "plan_node"
        }

    logger.info(f"Generating structured plan for task {state['task_id']}")
    start_t = time.perf_counter()

    try:
        plan: ExecutionPlan = await planner_service.create_plan(state["objective"])
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {
            "status": "FAILED",
            "current_node": "plan_node",
            "error_summary": f"Planning failure: {str(e)}"
        }

    duration = (time.perf_counter() - start_t) * 1000

    steps_map: Dict[str, StepState] = {}
    for step in plan.steps:
        # Check tool registry to see if approval is required
        tool = tool_registry.get_tool(step.tool_name) if tool_registry.has_tool(step.tool_name) else None
        requires_app = step.requires_approval or (tool.requires_approval if tool else False)

        steps_map[step.step_id] = StepState(
            step_id=step.step_id,
            step_name=step.step_name,
            tool_name=step.tool_name,
            arguments=step.arguments,
            dependencies=step.dependencies,
            expected_output=step.expected_output,
            status="PENDING",
            result=None,
            error=None,
            retry_count=0,
            requires_approval=requires_app,
            approval_id=None
        )

    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "plan_node",
        "duration_ms": duration,
        "plan_steps_count": len(plan.steps)
    }

    return {
        "plan": plan.model_dump(),
        "steps": steps_map,
        "status": "PLANNING",
        "current_node": "plan_node",
        "model_call_counter": state.get("model_call_counter", 0) + 1,
        "execution_trace": state.get("execution_trace", []) + [trace_entry]
    }


async def validate_plan_node(state: GraphState) -> Dict[str, Any]:
    """Validate generated plan against deterministic policy engine."""
    logger.info(f"Validating plan for task {state['task_id']}")
    plan_dict = state.get("plan")

    if not plan_dict:
        return {
            "status": "FAILED",
            "current_node": "validate_plan_node",
            "error_summary": "No plan found in graph state to validate."
        }

    try:
        plan = ExecutionPlan.model_validate(plan_dict)
        plan_policy_engine.validate_plan(plan)
    except PolicyViolationException as e:
        logger.warning(f"Plan policy rejection: {e.message}")
        return {
            "status": "FAILED",
            "current_node": "validate_plan_node",
            "error_summary": f"Policy rejection: {e.message}"
        }

    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "validate_plan_node",
        "event": "Plan validated successfully against policy engine"
    }

    return {
        "status": "RUNNING",
        "current_node": "validate_plan_node",
        "execution_trace": state.get("execution_trace", []) + [trace_entry]
    }


async def select_step_node(state: GraphState) -> Dict[str, Any]:
    """Select next runnable step based on dependency graph topology and deadline checks."""
    if _is_deadline_exceeded(state):
        return {
            "status": "FAILED",
            "current_node": "select_step_node",
            "error_summary": "Task deadline exceeded during execution"
        }

    if state.get("is_cancelled"):
        return {
            "status": "CANCELLED",
            "current_node": "select_step_node",
            "error_summary": "Task was cancelled by user"
        }

    completed = set(state.get("completed_step_ids", []))
    steps = state.get("steps", {})

    next_step_id: Optional[str] = None

    for s_id, s_data in steps.items():
        if s_data["status"] in ("COMPLETED", "FAILED", "SKIPPED"):
            continue
        deps = s_data.get("dependencies", [])
        if all(dep in completed for dep in deps):
            next_step_id = s_id
            break

    if next_step_id:
        steps_copy = copy.deepcopy(steps)
        req_app = steps_copy[next_step_id].get("requires_approval", False)
        decision_obj = state.get("approval_decision")
        is_decided = decision_obj and decision_obj.get("decision") == "APPROVED"

        status_val = "PAUSED_APPROVAL" if (req_app and not is_decided) else "RUNNING"
        steps_copy[next_step_id]["status"] = status_val

        return {
            "current_step_id": next_step_id,
            "steps": steps_copy,
            "status": status_val,
            "current_node": "select_step_node"
        }

    return {
        "current_step_id": None,
        "current_node": "select_step_node"
    }


async def approval_gate_node(state: GraphState) -> Dict[str, Any]:
    """Human-in-the-loop approval gate.
    Pauses execution via interrupt() if step requires authorization and no decision is present.
    """
    step_id = state.get("current_step_id")
    steps = state.get("steps", {})
    if not step_id or step_id not in steps:
        return {"current_node": "approval_gate_node"}

    step = steps[step_id]
    tool_name = step["tool_name"]
    raw_args = step.get("arguments", {})
    step_outputs = state.get("step_outputs", {})
    resolved_args = _resolve_template_references(raw_args, step_outputs)

    # Check if we already received a decision from a resume invocation
    decision_obj = state.get("approval_decision")
    if decision_obj and decision_obj.get("decision"):
        decision = decision_obj.get("decision")
        logger.info(f"Approval gate resumed for step '{step_id}' with decision: {decision}")

        if decision == "APPROVED":
            return {
                "status": "RUNNING",
                "current_node": "approval_gate_node",
                "pending_approval": None,
                "execution_trace": state.get("execution_trace", []) + [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "node": "approval_gate_node",
                    "event": f"Human approval granted for step '{step_id}'"
                }]
            }
        else:
            # Rejection
            steps_copy = copy.deepcopy(steps)
            steps_copy[step_id]["status"] = "FAILED"
            steps_copy[step_id]["error"] = f"Action rejected by reviewer: {decision_obj.get('notes')}"
            return {
                "steps": steps_copy,
                "status": "FAILED",
                "current_node": "approval_gate_node",
                "pending_approval": None,
                "error_summary": f"Human reviewer rejected sensitive operation '{tool_name}' in step '{step_id}'",
                "execution_trace": state.get("execution_trace", []) + [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "node": "approval_gate_node",
                    "event": f"Human approval rejected for step '{step_id}'"
                }]
            }

    # If no decision yet, construct approval request and pause workflow
    approval_id = str(uuid.uuid4())
    op_hash = compute_operation_hash(tool_name, resolved_args, state["task_id"])
    from datetime import timedelta
    expiry_dt = datetime.now(timezone.utc) + timedelta(seconds=settings.APPROVAL_TIMEOUT_SECONDS)

    # Persist approval request to database
    from app.db.session import AsyncSessionLocal
    from app.repositories.approval_repo import ApprovalRepository
    from app.repositories.task_repo import TaskRepository
    async with AsyncSessionLocal() as session:
        app_repo = ApprovalRepository(session)
        await app_repo.create_request(
            approval_id=approval_id,
            task_id=state["task_id"],
            step_id=step_id,
            tool_name=tool_name,
            operation_hash=op_hash,
            payload_summary=resolved_args,
            risk_level="CRITICAL",
            reason=f"Execution of sensitive operation '{tool_name}' requires explicit sign-off",
            expires_at=expiry_dt
        )
        task_repo = TaskRepository(session)
        await task_repo.update_task_progress(task_id=state["task_id"], status="PAUSED_APPROVAL")
        await session.commit()

    logger.info(f"Pausing workflow for task {state['task_id']} awaiting approval ID {approval_id}")

    # Interrupt execution; workflow will pause and persist checkpoint here
    interrupt({
        "approval_id": approval_id,
        "task_id": state["task_id"],
        "step_id": step_id,
        "tool_name": tool_name,
        "operation_hash": op_hash,
        "message": f"Operation '{tool_name}' requires human approval"
    })

    return {
        "status": "PAUSED_APPROVAL",
        "current_node": "approval_gate_node",
        "pending_approval": {
            "approval_id": approval_id,
            "step_id": step_id,
            "tool_name": tool_name,
            "operation_hash": op_hash
        }
    }


async def execute_tool_node(state: GraphState) -> Dict[str, Any]:
    """Execute selected tool with resolved arguments, retry tracking, and backoff."""
    step_id = state.get("current_step_id")
    if not step_id or step_id not in state.get("steps", {}):
        return {"current_node": "execute_tool_node"}

    step = state["steps"][step_id]
    tool_name = step["tool_name"]
    raw_args = step.get("arguments", {})
    step_outputs = state.get("step_outputs", {})

    resolved_args = _resolve_template_references(raw_args, step_outputs)
    logger.info(f"Executing tool '{tool_name}' for step '{step_id}' (attempt {step.get('retry_count', 0) + 1})")

    tool = tool_registry.get_tool(tool_name)
    start_t = time.perf_counter()

    try:
        validated_input = tool.input_schema.model_validate(resolved_args)
        output_dto = await tool.execute(validated_input)
        result_dict = output_dto.model_dump()
        is_success = True
        error_msg = None
    except Exception as e:
        logger.error(f"Tool execution failed for '{tool_name}': {e}")
        result_dict = None
        is_success = False
        error_msg = str(e)

    duration = (time.perf_counter() - start_t) * 1000

    steps_copy = copy.deepcopy(state["steps"])
    steps_copy[step_id]["result"] = result_dict
    steps_copy[step_id]["error"] = error_msg

    outputs_copy = copy.deepcopy(step_outputs)

    if is_success:
        steps_copy[step_id]["status"] = "COMPLETED"
        if result_dict is not None:
            outputs_copy[step_id] = result_dict
    else:
        # Check if retryable
        retries = step.get("retry_count", 0)
        if retries < tool.max_retries:
            steps_copy[step_id]["retry_count"] = retries + 1
            steps_copy[step_id]["status"] = "PENDING"  # Mark for retry
            backoff_sec = 0.05 * (2 ** retries)        # Fast backoff for local performance
            logger.info(f"Scheduling retry {retries + 1}/{tool.max_retries} for step '{step_id}' after {backoff_sec}s")
            time.sleep(backoff_sec)
        else:
            steps_copy[step_id]["status"] = "FAILED"

    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "execute_tool_node",
        "step_id": step_id,
        "tool_name": tool_name,
        "duration_ms": duration,
        "is_success": is_success,
        "error": error_msg
    }

    return {
        "steps": steps_copy,
        "step_outputs": outputs_copy,
        "step_counter": state.get("step_counter", 0) + 1,
        "current_node": "execute_tool_node",
        "execution_trace": state.get("execution_trace", []) + [trace_entry]
    }


async def verify_result_node(state: GraphState) -> Dict[str, Any]:
    """Verify tool output against schema and step expectations."""
    step_id = state.get("current_step_id")
    if not step_id or step_id not in state.get("steps", {}):
        return {"current_node": "verify_result_node"}

    step = state["steps"][step_id]
    tool = tool_registry.get_tool(step["tool_name"])
    evidence_copy = copy.deepcopy(state.get("evidence", []))

    if step["status"] == "COMPLETED" and step["result"]:
        try:
            tool.output_schema.model_validate(step["result"])
            evidence_copy.append({
                "step_id": step_id,
                "tool_name": step["tool_name"],
                "data": step["result"]
            })
        except Exception as e:
            logger.warning(f"Verification output schema mismatch: {e}")
            steps_copy = copy.deepcopy(state["steps"])
            steps_copy[step_id]["status"] = "FAILED"
            steps_copy[step_id]["error"] = f"Output schema validation failure: {str(e)}"
            return {
                "steps": steps_copy,
                "current_node": "verify_result_node"
            }

    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "verify_result_node",
        "step_id": step_id,
        "verified": step["status"] == "COMPLETED"
    }

    return {
        "evidence": evidence_copy,
        "current_node": "verify_result_node",
        "execution_trace": state.get("execution_trace", []) + [trace_entry]
    }


async def replan_node(state: GraphState) -> Dict[str, Any]:
    """Controlled replan triggered after a permanent step failure."""
    replan_count = state.get("replan_counter", 0) + 1
    logger.info(f"Executing controlled replan (attempt {replan_count}/{state.get('max_replans', 2)})")

    # Degrade plan: mark failed step as SKIPPED and allow remaining independent steps to proceed
    steps_copy = copy.deepcopy(state.get("steps", {}))
    failed_steps = [s_id for s_id, s in steps_copy.items() if s["status"] == "FAILED"]
    for f_id in failed_steps:
        steps_copy[f_id]["status"] = "SKIPPED"

    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "replan_node",
        "event": f"Controlled replan executed; skipped failed steps: {failed_steps}"
    }

    return {
        "steps": steps_copy,
        "replan_counter": replan_count,
        "status": "RUNNING",
        "current_node": "replan_node",
        "execution_trace": state.get("execution_trace", []) + [trace_entry]
    }


async def decide_next_node(state: GraphState) -> Dict[str, Any]:
    """Decide continuation, step retry, controlled replan, or completion transition."""
    step_id = state.get("current_step_id")
    steps = state.get("steps", {})
    completed = list(state.get("completed_step_ids", []))
    failed = list(state.get("failed_step_ids", []))

    if step_id and step_id in steps:
        step_status = steps[step_id]["status"]
        if step_status == "COMPLETED":
            if step_id not in completed:
                completed.append(step_id)
        elif step_status == "FAILED":
            if step_id not in failed:
                failed.append(step_id)

    # If step is still PENDING (i.e. scheduled for retry), do not fail yet
    if step_id and step_id in steps and steps[step_id]["status"] == "PENDING":
        return {
            "current_node": "decide_next_node",
            "status": "RUNNING"
        }

    # If step has terminally failed
    if failed:
        replans = state.get("replan_counter", 0)
        max_replans = state.get("max_replans", 2)
        if replans < max_replans:
            return {
                "completed_step_ids": completed,
                "failed_step_ids": failed,
                "status": "REPLANNING",
                "current_node": "decide_next_node"
            }
        else:
            return {
                "completed_step_ids": completed,
                "failed_step_ids": failed,
                "status": "FAILED",
                "current_node": "decide_next_node",
                "error_summary": f"Step '{failed[-1]}' failed and max replans ({max_replans}) exhausted."
            }

    # Check if all steps are completed or skipped
    all_step_ids = list(steps.keys())
    is_all_done = len(all_step_ids) > 0 and all(
        steps[s]["status"] in ("COMPLETED", "SKIPPED") for s in all_step_ids
    )

    return {
        "completed_step_ids": completed,
        "failed_step_ids": failed,
        "status": "COMPLETED" if is_all_done else "RUNNING",
        "current_node": "decide_next_node"
    }


async def synthesize_report_node(state: GraphState) -> Dict[str, Any]:
    """Synthesize final outcome, summary, and terminal report from verified evidence."""
    logger.info(f"Synthesizing final report for task {state['task_id']}")
    step_outputs = state.get("step_outputs", {})

    final_report = None
    for s_id, out in step_outputs.items():
        if isinstance(out, dict) and "markdown_content" in out:
            final_report = out["markdown_content"]
            break

    if not final_report:
        lines = [
            f"# Workflow Execution Summary: {state['objective']}",
            f"Status: **{state.get('status', 'COMPLETED')}**",
            f"Completed Steps: {len(state.get('completed_step_ids', []))}",
            "",
            "## Verified Evidence"
        ]
        for ev in state.get("evidence", []):
            lines.append(f"- **Step {ev['step_id']}** ({ev['tool_name']}):")
            lines.append(f"  ```json\n  {ev['data']}\n  ```")
        final_report = "\n".join(lines)

    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "synthesize_report_node",
        "event": "Final report synthesized"
    }

    return {
        "final_report": final_report,
        "status": "COMPLETED",
        "current_node": "synthesize_report_node",
        "execution_trace": state.get("execution_trace", []) + [trace_entry]
    }
