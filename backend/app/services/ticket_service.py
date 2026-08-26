"""Ticket lifecycle and chat-context snapshot operations."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_trace import AgentTrace
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage


def _metadata_trace_id(metadata: dict | None) -> str | None:
    metadata = metadata or {}
    direct = metadata.get("trace_id")
    if isinstance(direct, str) and direct:
        return direct
    for key in ("agent_response", "route_response"):
        nested = metadata.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("trace_id"), str):
            return nested["trace_id"]
    return None


def _latest_trace_id(messages: list[Message]) -> str | None:
    for message in reversed(messages):
        trace_id = _metadata_trace_id(message.metadata_json)
        if trace_id:
            return trace_id
    return None


def create_ticket(
    db: Session,
    *,
    session_id: int,
    reason: str,
    priority: str = "medium",
    source: str = "user_request",
    trace_id: str | None = None,
) -> Ticket | None:
    """Create a ticket and snapshot the session conversation in one transaction."""
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
    if session is None:
        return None

    messages = list(
        db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_time.asc(), Message.id.asc())
        ).all()
    )
    latest_customer = next((item.content for item in reversed(messages) if item.role == "user"), "")
    try:
        ticket = Ticket(
            ticket_id=f"p-{uuid4().hex[:30]}",
            user_id=session.user_id,
            session_id=session.id,
            title=(latest_customer or session.title or reason)[:255],
            description=reason,
            priority=priority,
            status="open",
            source=source,
            trace_id=trace_id or _latest_trace_id(messages),
        )
        db.add(ticket)
        db.flush()
        ticket.ticket_id = f"T{datetime.now():%Y%m%d}{ticket.id:03d}"
        # ticket_messages references the public ticket_id rather than the numeric
        # primary key, so make the parent key update visible before child inserts.
        db.flush()
        db.add_all(
            [
                TicketMessage(
                    ticket_id=ticket.ticket_id,
                    sender_type="customer" if message.role == "user" else "ai",
                    content=message.content,
                    created_time=message.created_time,
                )
                for message in messages
            ]
        )
        db.commit()
        db.refresh(ticket)
        return ticket
    except Exception:
        db.rollback()
        raise


def list_tickets(
    db: Session,
    *,
    status: str | None = None,
    priority: str | None = None,
) -> list[Ticket]:
    statement = select(Ticket)
    if status:
        statement = statement.where(Ticket.status == status)
    if priority:
        statement = statement.where(Ticket.priority == priority)
    return list(
        db.scalars(statement.order_by(Ticket.created_time.desc(), Ticket.id.desc())).all()
    )


def get_ticket(db: Session, ticket_id: str) -> Ticket | None:
    return db.scalar(select(Ticket).where(Ticket.ticket_id == ticket_id))


def get_ticket_trace(db: Session, ticket: Ticket) -> AgentTrace | None:
    if not ticket.trace_id:
        return None
    return db.scalar(select(AgentTrace).where(AgentTrace.trace_id == ticket.trace_id))


def update_ticket_status(db: Session, ticket: Ticket, new_status: str) -> Ticket:
    ticket.status = new_status
    ticket.updated_time = datetime.now()
    db.commit()
    db.refresh(ticket)
    return ticket


def add_human_message(db: Session, ticket: Ticket, content: str) -> TicketMessage:
    try:
        message = TicketMessage(
            ticket_id=ticket.ticket_id,
            sender_type="human_agent",
            content=content,
        )
        ticket.updated_time = datetime.now()
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    except Exception:
        db.rollback()
        raise
