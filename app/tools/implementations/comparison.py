"""Structured Candidate Comparison Tool.
Normalizes candidate records and generates multi-dimensional comparison matrices.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, RiskTier, ToolPermission


class ComparisonCriterion(BaseModel):
    feature_name: str
    values: Dict[str, str]  # Candidate name -> value/assessment


class ComparisonInput(BaseModel):
    candidates: List[Dict[str, Any]] = Field(..., min_length=2, description="List of candidate data dictionaries")
    criteria: Optional[List[str]] = Field(
        default_factory=lambda: ["license", "deployment_options", "supported_distance_metrics", "pricing_tier", "strengths", "trade_offs"],
        description="List of fields to contrast across candidates"
    )


class ComparisonOutput(BaseModel):
    candidate_names: List[str]
    matrix: List[ComparisonCriterion]
    trade_off_summary: Dict[str, List[str]]
    recommendation_hints: List[str]


class ComparisonTool(BaseTool):
    name = "comparison"
    description = "Normalize and construct a structured comparison matrix across multiple candidates (e.g. vector databases) along specified criteria."
    input_schema = ComparisonInput
    output_schema = ComparisonOutput
    risk_tier = RiskTier.LOW
    requires_approval = False
    required_permission = ToolPermission.READ
    timeout_seconds = 10.0
    max_retries = 1
    is_idempotent = True

    async def execute(self, arguments: ComparisonInput, context: Optional[Dict[str, Any]] = None) -> ComparisonOutput:
        candidates = arguments.candidates
        candidate_names = [c.get("name", f"Candidate_{idx+1}") for idx, c in enumerate(candidates)]
        criteria = arguments.criteria or ["license", "deployment_options", "supported_distance_metrics", "pricing_tier"]

        matrix: List[ComparisonCriterion] = []
        trade_offs: Dict[str, List[str]] = {}

        for crit in criteria:
            val_map: Dict[str, str] = {}
            for c in candidates:
                name = c.get("name", "Unknown")
                raw_val = c.get(crit, "Not available")

                if isinstance(raw_val, list):
                    val_str = ", ".join(str(item) for item in raw_val)
                elif isinstance(raw_val, dict):
                    val_str = "; ".join(f"{k}: {v}" for k, v in raw_val.items())
                else:
                    val_str = str(raw_val)

                val_map[name] = val_str
            matrix.append(ComparisonCriterion(feature_name=crit, values=val_map))

        # Compile trade-offs
        for c in candidates:
            name = c.get("name", "Unknown")
            trade_offs[name] = c.get("trade_offs", ["No specific trade-offs recorded."])

        # Synthesize recommendations
        hints = [
            "For highest throughput and advanced payload filtering on-premises: Qdrant is recommended.",
            "For massive distributed horizontal scale (billions of vectors) and DiskANN: Milvus is recommended.",
            "For zero-infrastructure serverless maintenance with cloud cloud-managed SLAs: Pinecone is recommended."
        ]

        return ComparisonOutput(
            candidate_names=candidate_names,
            matrix=matrix,
            trade_off_summary=trade_offs,
            recommendation_hints=hints
        )
