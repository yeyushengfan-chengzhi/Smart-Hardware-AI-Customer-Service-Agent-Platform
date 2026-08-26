"""Agent trace persistence isolated from customer-facing request transactions."""

import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.agent_trace import AgentTrace

logger = logging.getLogger(__name__)


def save_trace_safely(**values) -> str:
    """Persist a trace and never propagate telemetry failures to the caller."""
    trace_id = values.pop("trace_id", None) or str(uuid4())
    db = SessionLocal()
    try:
        db.add(AgentTrace(trace_id=trace_id, **values))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist agent trace %s", trace_id)
    finally:
        db.close()
    return trace_id


def query_traces(
    db: Session,
    route: str | None,
    agent_name: str | None,
    status: str | None,
    limit: int,
) -> list[AgentTrace]:
    statement = select(AgentTrace)
    if route:
        statement = statement.where(AgentTrace.route == route)
    if agent_name:
        statement = statement.where(AgentTrace.agent_name == agent_name)
    if status:
        statement = statement.where(AgentTrace.status == status)
    return list(db.scalars(statement.order_by(AgentTrace.created_time.desc(), AgentTrace.id.desc()).limit(limit)).all())


def get_trace(db: Session, trace_id: str) -> AgentTrace | None:
    return db.scalar(select(AgentTrace).where(AgentTrace.trace_id == trace_id))
