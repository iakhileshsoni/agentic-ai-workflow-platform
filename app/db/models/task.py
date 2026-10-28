"""Task Entity Model."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"

    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", index=True, nullable=False)
    current_node: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    plan_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)

    # Relationships
    steps: Mapped[List["TaskStep"]] = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    approvals: Mapped[List["ApprovalRequest"]] = relationship("ApprovalRequest", back_populates="task", cascade="all, delete-orphan")
