"""Password and JWT helpers for authentication."""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import get_settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plaintext password."""
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against its stored hash."""
    return password_context.verify(password, password_hash)


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create an expiring JWT for an authenticated user."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "username": username, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
