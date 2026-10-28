"""Deterministic Calculator Tool.
Performs safe arithmetic operations without eval().
"""
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.core.exceptions import ToolExecutionException
from app.tools.base import BaseTool, RiskTier, ToolPermission


class CalcOperation(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    PERCENTAGE = "percentage"


class CalculatorInput(BaseModel):
    operation: CalcOperation = Field(..., description="Arithmetic operation to perform")
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")


class CalculatorOutput(BaseModel):
    operation: str
    a: float
    b: float
    result: float
    formula: str


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Perform safe, deterministic arithmetic calculations (add, subtract, multiply, divide, percentage)."
    input_schema = CalculatorInput
    output_schema = CalculatorOutput
    risk_tier = RiskTier.LOW
    requires_approval = False
    required_permission = ToolPermission.READ
    timeout_seconds = 5.0
    max_retries = 1
    is_idempotent = True

    async def execute(self, arguments: CalculatorInput, context: Optional[Dict[str, Any]] = None) -> CalculatorOutput:
        op = arguments.operation
        a = arguments.a
        b = arguments.b

        if op == CalcOperation.ADD:
            res = a + b
            formula = f"{a} + {b} = {res}"
        elif op == CalcOperation.SUBTRACT:
            res = a - b
            formula = f"{a} - {b} = {res}"
        elif op == CalcOperation.MULTIPLY:
            res = a * b
            formula = f"{a} * {b} = {res}"
        elif op == CalcOperation.DIVIDE:
            if b == 0:
                raise ToolExecutionException("Division by zero is not permitted", is_recoverable=False)
            res = a / b
            formula = f"{a} / {b} = {res}"
        elif op == CalcOperation.PERCENTAGE:
            if b == 0:
                raise ToolExecutionException("Base value for percentage calculation cannot be zero", is_recoverable=False)
            res = (a / b) * 100
            formula = f"({a} / {b}) * 100 = {res:.2f}%"
        else:
            raise ToolExecutionException(f"Unsupported operation: {op}", is_recoverable=False)

        return CalculatorOutput(
            operation=op.value,
            a=a,
            b=b,
            result=round(res, 4),
            formula=formula
        )
