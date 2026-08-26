"""Registration and login endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.services.auth_service import create_access_token, verify_password
from app.services.user_service import create_user, get_user_by_username


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    """Register a customer account."""
    if get_user_by_username(db, payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        )

    create_user(db, payload.username, payload.password)
    return RegisterResponse(message="register success")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and issue a JWT access token."""
    user = get_user_by_username(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect username or password",
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.username, user.role)
    )
