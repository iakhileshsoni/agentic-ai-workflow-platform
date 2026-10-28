"""Task Step Execution Model."""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class TaskStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_steps"

    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), index=True, nullable=False)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)
    input_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship("Task", back_populates="steps")
