from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.models.user import User
from app.security import get_current_user, require_admin, require_support


def build_role_client(role: str) -> TestClient:
    app = FastAPI()

    @app.get("/support", dependencies=[Depends(require_support)])
    def support_route():
        return {"ok": True}

    @app.get("/admin", dependencies=[Depends(require_admin)])
    def admin_route():
        return {"ok": True}

    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        username=f"{role}-demo",
        password_hash="hash",
        role=role,
    )
    return TestClient(app)


def test_user_cannot_access_support_or_admin_routes():
    client = build_role_client("user")
    assert client.get("/support").status_code == 403
    assert client.get("/admin").status_code == 403


def test_agent_can_access_support_but_not_admin_routes():
    client = build_role_client("agent")
    assert client.get("/support").status_code == 200
    assert client.get("/admin").status_code == 403


def test_admin_can_access_support_and_admin_routes():
    client = build_role_client("admin")
    assert client.get("/support").status_code == 200
    assert client.get("/admin").status_code == 200
