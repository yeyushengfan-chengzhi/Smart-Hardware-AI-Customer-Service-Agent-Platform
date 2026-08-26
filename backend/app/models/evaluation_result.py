"""Per-case result produced by an evaluation run."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cases.id"), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    actual_route: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    expected_route: Mapped[str] = mapped_column(String(32), nullable=False)
    route_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actual_agent: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    expected_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expected_tool: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actual_tool: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tool_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="failed", index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
