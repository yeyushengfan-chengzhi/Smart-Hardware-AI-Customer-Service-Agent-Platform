"""User persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth_service import hash_password


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
