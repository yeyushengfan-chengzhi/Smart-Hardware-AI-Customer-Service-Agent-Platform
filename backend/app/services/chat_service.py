"""Customer-service chat persistence operations."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.message import Message


FIXED_ANSWER = "您的问题已记录，客服助手正在处理中"


def get_or_create_session(db: Session, user_id: int, first_message: str) -> ChatSession:
    """Return the user's latest session, or create one from the first message."""
    session = db.scalar(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.id.desc())
        .limit(1)
    )
    if session is None:
        session = ChatSession(user_id=user_id, title=first_message[:255])
        db.add(session)
        db.flush()
    return session


def create_chat_reply(db: Session, user_id: int, content: str) -> str:
    """Store the user message and fixed assistant reply in one transaction."""
    try:
        session = get_or_create_session(db, user_id, content)
        db.add_all(
            [
                Message(session_id=session.id, role="user", content=content),
                Message(session_id=session.id, role="assistant", content=FIXED_ANSWER),
            ]
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return FIXED_ANSWER


def get_user_history(db: Session, user_id: int) -> list[Message]:
    """Return all messages belonging to the user in chronological order."""
    return list(
        db.scalars(
            select(Message)
            .join(ChatSession, Message.session_id == ChatSession.id)
            .where(ChatSession.user_id == user_id)
            .order_by(Message.created_time.asc(), Message.id.asc())
        ).all()
    )


def create_session(db: Session, user_id: int, title: str) -> ChatSession:
    session = ChatSession(user_id=user_id, title=title[:255])
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, user_id: int) -> list[tuple[ChatSession, str]]:
    sessions = list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_time.desc(), ChatSession.id.desc())
        ).all()
    )
    return [
        (session, session.messages[-1].content if session.messages else "")
        for session in sessions
    ]


def get_session(db: Session, user_id: int, session_id: int) -> ChatSession | None:
    return db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )


def add_session_message(
    db: Session,
    session: ChatSession,
    role: str,
    content: str,
    metadata: dict,
) -> Message:
    message = Message(
        session_id=session.id,
        role=role,
        content=content,
        metadata_json=metadata,
    )
    session.updated_time = datetime.now()
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
