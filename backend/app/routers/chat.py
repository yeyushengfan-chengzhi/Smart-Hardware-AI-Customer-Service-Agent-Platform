"""Authenticated customer-service chat endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import get_current_user
from app.schemas import (
    ChatMessageCreateRequest,
    ChatRequest,
    ChatResponse,
    ChatSessionCreateRequest,
    ChatSessionMessageResponse,
    ChatSessionResponse,
    HistoryMessageResponse,
)
from app.services.chat_service import (
    add_session_message,
    create_chat_reply,
    create_session,
    get_session,
    get_user_history,
    list_sessions,
)


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Save a customer message and return the fixed service response."""
    answer = create_chat_reply(db, current_user.id, payload.message)
    return ChatResponse(answer=answer)


@router.get("/chat/history", response_model=list[HistoryMessageResponse])
def chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryMessageResponse]:
    """Return the authenticated user's complete message history."""
    history = get_user_history(db, current_user.id)
    return [HistoryMessageResponse.model_validate(item) for item in history]


@router.post("/chat/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    session = create_session(db, current_user.id, payload.title)
    return ChatSessionResponse(
        session_id=session.id,
        title=session.title,
        created_time=session.created_time,
        updated_time=session.updated_time,
    )


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionResponse]:
    return [
        ChatSessionResponse(
            session_id=session.id,
            title=session.title,
            last_message=last_message,
            created_time=session.created_time,
            updated_time=session.updated_time,
        )
        for session, last_message in list_sessions(db, current_user.id)
    ]


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatSessionMessageResponse])
def get_chat_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionMessageResponse]:
    session = get_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found")
    return [
        ChatSessionMessageResponse(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            metadata=message.metadata_json or {},
            created_time=message.created_time,
        )
        for message in session.messages
    ]


@router.post(
    "/chat/sessions/{session_id}/messages",
    response_model=ChatSessionMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_chat_session_message(
    session_id: int,
    payload: ChatMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionMessageResponse:
    session = get_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found")
    message = add_session_message(db, session, payload.role, payload.content, payload.metadata)
    return ChatSessionMessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        metadata=message.metadata_json or {},
        created_time=message.created_time,
    )
