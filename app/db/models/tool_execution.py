"""Tool Execution Trace Log Model."""
from typing import Optional
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ToolExecutionLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tool_execution_logs"

    task_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    output_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
