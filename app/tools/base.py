"""Base Tool Abstraction.
Defines typing, metadata, risk tiers, permissions, and execution interface for all tools.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    LOW = "LOW"             # Read-only deterministic arithmetic or local fixture lookup
    MEDIUM = "MEDIUM"       # Local file access or cache mutation
    HIGH = "HIGH"           # External simulated actions, exports, disk writes
    CRITICAL = "CRITICAL"   # State changes requiring human sign-off


class ToolPermission(str, Enum):
    READ = "tool:read"
    MUTATE = "tool:mutate"
    ADMIN = "tool:admin"


class BaseTool(ABC):
    """Abstract base class for all platform tools.
    Every tool must define explicit Pydantic input and output schemas.
    """
    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    risk_tier: RiskTier = RiskTier.LOW
    requires_approval: bool = False
    required_permission: ToolPermission = ToolPermission.READ
    timeout_seconds: float = 15.0
    max_retries: int = 2
    is_idempotent: bool = True

    @abstractmethod
    async def execute(self, arguments: BaseModel, context: Optional[Dict[str, Any]] = None) -> BaseModel:
        """Execute the tool business logic with validated arguments."""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Return structured tool metadata for planning and documentation."""
        return {
            "name": self.name,
            "description": self.description,
            "risk_tier": self.risk_tier.value,
            "requires_approval": self.requires_approval,
            "required_permission": self.required_permission.value,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "is_idempotent": self.is_idempotent,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
        }
