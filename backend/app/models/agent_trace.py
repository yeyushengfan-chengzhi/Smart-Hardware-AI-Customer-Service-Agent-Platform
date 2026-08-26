"""Persistent execution trace for one completed Agent request."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    intent: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    device_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    fault_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    final_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sources_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tool_input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tool_result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    route_response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    agent_response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    handoff_suggested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handoff_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success", index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
