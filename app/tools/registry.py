"""Tool Registry Singleton.
Provides discovery, schema inspection, authorization, and dispatch for all registered tools.
"""
from typing import Dict, List, Optional
from app.core.exceptions import PlatformException, ErrorCategory
from app.tools.base import BaseTool
from app.tools.implementations import (
    CalculatorTool,
    DatasetSearchTool,
    DocSearchTool,
    ComparisonTool,
    ReportGeneratorTool,
    ResultValidatorTool,
)


class ToolRegistry:
    """Thread-safe catalog of typed tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register default offline tools."""
        self.register(CalculatorTool())
        self.register(DatasetSearchTool())
        self.register(DocSearchTool())
        self.register(ComparisonTool())
        self.register(ReportGeneratorTool())
        self.register(ResultValidatorTool())

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if tool.name in self._tools:
            raise PlatformException(
                f"Tool '{tool.name}' is already registered",
                category=ErrorCategory.POLICY_VIOLATION
            )
        self._tools[tool.name] = tool

    def get_tool(self, tool_name: str) -> BaseTool:
        """Lookup tool by name or raise error."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise PlatformException(
                f"Tool '{tool_name}' not found in registry",
                category=ErrorCategory.POLICY_VIOLATION,
                details={"available_tools": list(self._tools.keys())}
            )
        return tool

    def has_tool(self, tool_name: str) -> bool:
        """Check if tool exists."""
        return tool_name in self._tools

    def list_tools(self) -> List[Dict[str, any]]:
        """List metadata for all registered tools."""
        return [tool.get_metadata() for tool in self._tools.values()]

    def get_tool_catalog_summary(self) -> str:
        """Return human-readable tool catalog formatted for the planner LLM prompt."""
        lines = []
        for tool in self._tools.values():
            meta = tool.get_metadata()
            lines.append(f"- Tool: `{tool.name}`")
            lines.append(f"  Description: {tool.description}")
            lines.append(f"  Risk Tier: {tool.risk_tier.value}")
            lines.append(f"  Requires Approval: {tool.requires_approval}")
            lines.append(f"  Input Schema: {meta['input_schema'].get('properties', {})}")
        return "\n".join(lines)


# Global registry singleton
tool_registry = ToolRegistry()
