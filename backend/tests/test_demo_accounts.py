from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.models.user import User
from app.routers import dev
from app.services.auth_service import verify_password


def build_client(monkeypatch, app_env: str = "development") -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    app = FastAPI()
    app.include_router(dev.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(dev, "get_settings", lambda: SimpleNamespace(app_env=app_env))
    return TestClient(app), db


def test_seed_demo_accounts_creates_and_normalizes_all_roles(monkeypatch):
    client, db = build_client(monkeypatch)
    db.add(User(username="agent_demo", password_hash="outdated", role="user"))
    db.commit()

    first = client.post("/api/dev/seed-demo-accounts")
    second = client.post("/api/dev/seed-demo-accounts")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {
        "accounts": [
            {"username": "user_demo", "role": "user"},
            {"username": "agent_demo", "role": "agent"},
            {"username": "admin_demo", "role": "admin"},
        ]
    }
    assert "123456" not in first.text

    users = {
        user.username: user
        for user in db.scalars(
            select(User).where(
                User.username.in_(["user_demo", "agent_demo", "admin_demo"])
            )
        )
    }
    assert {username: user.role for username, user in users.items()} == {
        "user_demo": "user",
        "agent_demo": "agent",
        "admin_demo": "admin",
    }
    assert all(verify_password("123456", user.password_hash) for user in users.values())


def test_seed_demo_accounts_is_disabled_in_production(monkeypatch):
    client, db = build_client(monkeypatch, app_env="production")

    response = client.post("/api/dev/seed-demo-accounts")

    assert response.status_code == 404
    assert db.scalar(select(User).where(User.username == "admin_demo")) is None
