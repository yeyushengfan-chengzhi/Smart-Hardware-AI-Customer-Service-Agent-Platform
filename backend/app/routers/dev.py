"""Local-development helpers that are unavailable in production."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas import DemoAccountResponse, DemoAccountsResponse
from app.services.auth_service import hash_password


router = APIRouter(prefix="/dev", tags=["development"])

DEMO_PASSWORD = "123456"
DEMO_ACCOUNTS = (
    ("user_demo", "user"),
    ("agent_demo", "agent"),
    ("admin_demo", "admin"),
)


@router.post("/seed-demo-accounts", response_model=DemoAccountsResponse)
def seed_demo_accounts(db: Session = Depends(get_db)) -> DemoAccountsResponse:
    """Create or normalize the local demo accounts without exposing passwords."""
    if get_settings().app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="demo account initialization is disabled in production",
        )

    accounts: list[DemoAccountResponse] = []
    for username, role in DEMO_ACCOUNTS:
        user = db.scalar(select(User).where(User.username == username))
        password_hash = hash_password(DEMO_PASSWORD)
        if user is None:
            user = User(username=username, password_hash=password_hash, role=role)
            db.add(user)
        else:
            user.password_hash = password_hash
            user.role = role
        accounts.append(DemoAccountResponse(username=username, role=role))

    db.commit()
    return DemoAccountsResponse(accounts=accounts)
