"""Domain Exceptions and Failure Classifications.
Categorizes recoverable vs terminal errors across planning, policy, tools, and execution.
"""
from enum import Enum
from typing import Optional, Dict, Any


class ErrorCategory(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    TRANSIENT_TOOL_FAILURE = "TRANSIENT_TOOL_FAILURE"
    PERMANENT_TOOL_FAILURE = "PERMANENT_TOOL_FAILURE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    INVALID_TOOL_OUTPUT = "INVALID_TOOL_OUTPUT"
    LLM_PARSING_FAILURE = "LLM_PARSING_FAILURE"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_TIMEOUT = "APPROVAL_TIMEOUT"
    TASK_CANCELLED = "TASK_CANCELLED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    CHECKPOINT_FAILURE = "CHECKPOINT_FAILURE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class PlatformException(Exception):
    """Base exception for platform domain errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.PERMANENT_TOOL_FAILURE,
        details: Optional[Dict[str, Any]] = None,
        is_recoverable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.details = details or {}
        self.is_recoverable = is_recoverable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_category": self.category.value,
            "message": self.message,
            "is_recoverable": self.is_recoverable,
            "details": self.details,
        }


class PolicyViolationException(PlatformException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.POLICY_VIOLATION,
            details=details,
            is_recoverable=False,
        )


class ToolExecutionException(PlatformException):
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.TRANSIENT_TOOL_FAILURE,
        is_recoverable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            category=category,
            details=details,
            is_recoverable=is_recoverable,
        )


class ApprovalException(PlatformException):
    def __init__(self, message: str, is_rejected: bool = True):
        category = ErrorCategory.APPROVAL_REJECTED if is_rejected else ErrorCategory.APPROVAL_TIMEOUT
        super().__init__(
            message=message,
            category=category,
            is_recoverable=False,
        )


class DeadlineExceededException(PlatformException):
    def __init__(self, message: str = "Workflow execution exceeded maximum permitted deadline"):
        super().__init__(
            message=message,
            category=ErrorCategory.DEADLINE_EXCEEDED,
            is_recoverable=False,
        )
