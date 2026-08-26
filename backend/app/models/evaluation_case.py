"""Rule-based evaluation test case."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_route: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expected_tool: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="general", index=True)
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
