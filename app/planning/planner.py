"""Structured Planner Service.
Coordinates the LLM adapter and ensures plan schema adherence.
"""
from app.planning.llm_adapter import llm_adapter, LLMAdapter
from app.schemas.plan import ExecutionPlan
from app.tools.registry import tool_registry, ToolRegistry


class PlannerService:
    """Generates strictly typed execution plans for workflows."""

    def __init__(self, adapter: LLMAdapter = llm_adapter, registry: ToolRegistry = tool_registry):
        self.adapter = adapter
        self.registry = registry

    async def create_plan(self, objective: str) -> ExecutionPlan:
        """Create structured execution plan for given objective."""
        catalog_summary = self.registry.get_tool_catalog_summary()
        return await self.adapter.generate_plan(objective, catalog_summary)


planner_service = PlannerService()
