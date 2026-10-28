"""Result and Evidence Completeness Validator Tool.
Deterministic verification that execution outputs meet criteria before finalizing.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, RiskTier, ToolPermission


class ValidatorInput(BaseModel):
    step_outputs: Dict[str, Any] = Field(..., description="Map of step_id to step output data")
    required_fields: List[str] = Field(..., description="Fields that must exist in the accumulated evidence")
    min_evidence_items: int = Field(default=1, ge=1, description="Minimum number of verified data points required")


class ValidatorOutput(BaseModel):
    is_valid: bool
    missing_fields: List[str]
    evidence_count: int
    validation_notes: List[str]


class ResultValidatorTool(BaseTool):
    name = "result_validator"
    description = "Validate that collected evidence and intermediate step outputs contain all required fields and satisfy completion rules."
    input_schema = ValidatorInput
    output_schema = ValidatorOutput
    risk_tier = RiskTier.LOW
    requires_approval = False
    required_permission = ToolPermission.READ
    timeout_seconds = 5.0
    max_retries = 1
    is_idempotent = True

    async def execute(self, arguments: ValidatorInput, context: Optional[Dict[str, Any]] = None) -> ValidatorOutput:
        outputs = arguments.step_outputs
        reqs = arguments.required_fields
        missing: List[str] = []
        notes: List[str] = []

        # Flatten output keys
        all_keys = set()
        total_items = 0

        def extract_keys(obj: Any):
            nonlocal total_items
            if isinstance(obj, dict):
                total_items += 1
                for k, v in obj.items():
                    all_keys.add(k)
                    extract_keys(v)
            elif isinstance(obj, list):
                total_items += len(obj)
                for item in obj:
                    extract_keys(item)

        extract_keys(outputs)

        for rf in reqs:
            if rf not in all_keys:
                missing.append(rf)

        is_valid = len(missing) == 0 and total_items >= arguments.min_evidence_items

        if is_valid:
            notes.append("All required fields confirmed present in collected evidence bank.")
            notes.append(f"Evidence quantity check passed ({total_items} items >= threshold {arguments.min_evidence_items}).")
        else:
            if missing:
                notes.append(f"Missing required fields: {', '.join(missing)}")
            if total_items < arguments.min_evidence_items:
                notes.append(f"Insufficient evidence items: found {total_items}, required at least {arguments.min_evidence_items}")

        return ValidatorOutput(
            is_valid=is_valid,
            missing_fields=missing,
            evidence_count=total_items,
            validation_notes=notes
        )
