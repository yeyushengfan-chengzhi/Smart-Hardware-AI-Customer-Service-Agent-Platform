"""Persisted, admin-managed configuration for the existing agents."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    enabled_tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    knowledge_binding: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
