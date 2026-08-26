from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.agent_trace import AgentTrace
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.ticket_message import TicketMessage
from app.models.user import User
from app.routers.tickets import router
from app.security import get_current_user


def build_client(role: str = "admin") -> tuple[TestClient, Session, int]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(username="ticket-user", password_hash="hash", role=role)
    db.add(user)
    db.flush()
    chat_session = ChatSession(user_id=user.id, title="显卡兼容性问题")
    db.add(chat_session)
    db.flush()
    trace = AgentTrace(
        trace_id="ticket-trace-1",
        query="这张显卡兼容吗",
        route="ToolAgent",
        intent="compatibility_check",
        device_type="gpu",
        fault_type="unknown",
        agent_name="ToolAgent",
        final_answer="暂时无法确认兼容性",
        sources_json=[],
        tool_name="check_compatibility",
        tool_input_json={},
        tool_result_json={"compatible": "unknown"},
        route_response_json={},
        agent_response_json={"compatible": "unknown"},
        latency_json={},
        handoff_suggested=True,
        handoff_reason="tool_unknown",
        status="success",
        error_message="",
    )
    db.add(trace)
    db.add_all(
        [
            Message(session_id=chat_session.id, role="user", content="这张显卡兼容吗"),
            Message(
                session_id=chat_session.id,
                role="assistant",
                content="暂时无法确认兼容性",
                metadata_json={"trace_id": trace.trace_id, "handoff_suggested": True},
            ),
        ]
    )
    db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), db, chat_session.id


def test_ticket_api_closes_the_handoff_lifecycle():
    client, db, session_id = build_client()

    created = client.post(
        "/api/tickets",
        json={
            "session_id": session_id,
            "reason": "AI无法确认硬件兼容性",
            "source": "ai_handoff",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["ticket_id"]
    assert ticket_id.startswith(f"T{datetime.now():%Y%m%d}")
    assert created.json()["status"] == "open"

    listed = client.get("/api/tickets", params={"status": "open", "priority": "medium"})
    assert listed.status_code == 200
    assert [item["ticket_id"] for item in listed.json()] == [ticket_id]

    detail = client.get(f"/api/tickets/{ticket_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["session_id"] == session_id
    assert payload["trace_id"] == "ticket-trace-1"
    assert payload["agent_name"] == "ToolAgent"
    assert payload["handoff_reason"] == "tool_unknown"
    assert [item["sender_type"] for item in payload["messages"]] == ["customer", "ai"]
    assert [item["content"] for item in payload["messages"]] == [
        "这张显卡兼容吗",
        "暂时无法确认兼容性",
    ]

    updated = client.patch(f"/api/tickets/{ticket_id}/status", json={"status": "processing"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "processing"

    reply = client.post(
        f"/api/tickets/{ticket_id}/messages",
        json={"sender_type": "human_agent", "content": "请提供主板型号和BIOS版本"},
    )
    assert reply.status_code == 201
    assert reply.json()["sender_type"] == "human_agent"
    stored = db.scalar(
        select(TicketMessage).where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.sender_type == "human_agent",
        )
    )
    assert stored is not None
    assert stored.content == "请提供主板型号和BIOS版本"


def test_create_ticket_rejects_unknown_session():
    client, db, _ = build_client()
    response = client.post(
        "/api/tickets",
        json={"session_id": 99999, "reason": "转人工"},
    )
    assert response.status_code == 404
    db.close()


def test_customer_can_create_and_read_own_ticket_but_cannot_manage_queue():
    client, db, session_id = build_client(role="user")
    created = client.post(
        "/api/tickets",
        json={"session_id": session_id, "reason": "需要人工确认", "source": "user_request"},
    )
    assert created.status_code == 201
    assert client.get("/api/tickets").status_code == 403
    ticket_url = f"/api/tickets/{created.json()['ticket_id']}"
    assert client.get(ticket_url).status_code == 200
    assert client.patch(ticket_url + "/status", json={"status": "processing"}).status_code == 403
    assert client.post(
        ticket_url + "/messages",
        json={"sender_type": "human_agent", "content": "forbidden"},
    ).status_code == 403

    stranger = User(username="ticket-stranger", password_hash="hash", role="user")
    db.add(stranger)
    db.commit()
    client.app.dependency_overrides[get_current_user] = lambda: stranger
    assert client.get(ticket_url).status_code == 403
    db.close()
