"""Human handoff and ticket-management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas import (
    TicketCreateRequest,
    TicketCreateResponse,
    TicketDetailResponse,
    TicketListItemResponse,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketPriority,
    TicketStatus,
    TicketStatusUpdateRequest,
)
from app.security import get_current_user, require_support
from app.services.chat_service import get_session
from app.services.ticket_service import (
    add_human_message,
    create_ticket,
    get_ticket,
    get_ticket_trace,
    list_tickets,
    update_ticket_status,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketCreateResponse, status_code=status.HTTP_201_CREATED)
def create_ticket_endpoint(
    payload: TicketCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketCreateResponse:
    if get_session(db, current_user.id, payload.session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found")
    ticket = create_ticket(
        db,
        session_id=payload.session_id,
        reason=payload.reason,
        priority=payload.priority,
        source=payload.source,
        trace_id=payload.trace_id,
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found")
    return TicketCreateResponse(ticket_id=ticket.ticket_id, status=ticket.status)


@router.get("", response_model=list[TicketListItemResponse])
def get_tickets(
    ticket_status: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: TicketPriority | None = None,
    _: User = Depends(require_support),
    db: Session = Depends(get_db),
) -> list[TicketListItemResponse]:
    return [
        TicketListItemResponse.model_validate(ticket, from_attributes=True)
        for ticket in list_tickets(db, status=ticket_status, priority=priority)
    ]


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket_detail(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketDetailResponse:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ticket not found")
    if current_user.role not in {"agent", "admin"} and ticket.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot access another user's ticket",
        )
    trace = get_ticket_trace(db, ticket)
    return TicketDetailResponse(
        ticket_id=ticket.ticket_id,
        user_id=ticket.user_id,
        session_id=ticket.session_id,
        title=ticket.title,
        description=ticket.description,
        source=ticket.source,
        status=ticket.status,
        priority=ticket.priority,
        trace_id=ticket.trace_id,
        agent_name=trace.agent_name if trace else None,
        handoff_reason=(trace.handoff_reason if trace and trace.handoff_reason else ticket.description),
        agent_result=(trace.agent_response_json if trace else {}),
        messages=[TicketMessageResponse.model_validate(item, from_attributes=True) for item in ticket.messages],
        created_time=ticket.created_time,
        updated_time=ticket.updated_time,
    )


@router.patch("/{ticket_id}/status", response_model=TicketCreateResponse)
def patch_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdateRequest,
    _: User = Depends(require_support),
    db: Session = Depends(get_db),
) -> TicketCreateResponse:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ticket not found")
    ticket = update_ticket_status(db, ticket, payload.status)
    return TicketCreateResponse(ticket_id=ticket.ticket_id, status=ticket.status)


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_ticket_message(
    ticket_id: str,
    payload: TicketMessageCreateRequest,
    _: User = Depends(require_support),
    db: Session = Depends(get_db),
) -> TicketMessageResponse:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ticket not found")
    message = add_human_message(db, ticket, payload.content)
    return TicketMessageResponse.model_validate(message, from_attributes=True)
