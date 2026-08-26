"""Conversation persistence operations."""

from sqlalchemy.orm import Session

from app.models.conversation import Conversation


def create_conversation(db: Session, user_id: int, question: str, answer: str) -> Conversation:
    conversation = Conversation(user_id=user_id, question=question, answer=answer)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation
