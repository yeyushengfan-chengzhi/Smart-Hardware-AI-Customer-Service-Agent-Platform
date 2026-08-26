"""Immutable prompt history for Agent Management Center."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentPromptVersion(Base):
    __tablename__ = "agent_prompt_versions"
    __table_args__ = (UniqueConstraint("agent_name", "version", name="uq_agent_prompt_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
