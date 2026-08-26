from app.routers import agent as agent_router
from app.schemas import AgentKnowledgeRequest, AgentToolRequest
from app.services import trace_service


def test_tool_trace_contains_structured_tool_result(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_router, "save_trace_safely", lambda **values: captured.update(values) or "trace-1")

    response = agent_router.call_hardware_tool(AgentToolRequest(query="9700X可以搭配B850主板吗"))

    assert response.trace_id == "trace-1"
    assert captured["agent_name"] == "ToolAgent"
    assert captured["tool_name"] == "pc_build_compatibility_tool"
    assert captured["tool_result_json"]["compatible"] == "yes"
    assert captured["status"] == "success"


def test_unknown_tool_result_suggests_handoff(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_router, "save_trace_safely", lambda **values: captured.update(values) or "trace-2")

    response = agent_router.call_hardware_tool(AgentToolRequest(query="未知型号CPU可以搭配B850主板吗"))

    assert response.tool_result["compatible"] == "unknown"
    assert captured["handoff_suggested"] is True
    assert captured["handoff_reason"] == "tool_unknown"


def test_trace_failure_is_swallowed(monkeypatch):
    class BrokenSession:
        def add(self, _): raise RuntimeError("trace database unavailable")
        def rollback(self): pass
        def close(self): pass

    monkeypatch.setattr(trace_service, "SessionLocal", BrokenSession)
    trace_id = trace_service.save_trace_safely(
        query="query", route="tool", intent="compatibility_check",
        device_type="motherboard", fault_type="unknown", agent_name="ToolAgent",
        final_answer="answer", sources_json=[], tool_name="", tool_input_json={},
        tool_result_json={}, route_response_json={}, agent_response_json={}, latency_json={},
        handoff_suggested=False, handoff_reason="", status="success", error_message="",
    )
    assert trace_id


def test_lancool_knowledge_trace_keeps_sources(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        agent_router.knowledge_agent,
        "answer",
        lambda query, top_k: {
            "query": query,
            "answer": "LANCOOL 216 支持 360 mm 冷排。",
            "sources": [{
                "filename": "LIAN_LI_LANCOOL_216_case_manual.pdf",
                "page_number": 1,
                "section_title": "Case Components",
            }],
        },
    )
    monkeypatch.setattr(
        agent_router,
        "save_trace_safely",
        lambda **values: captured.update(values) or "trace-lancool",
    )

    response = agent_router.answer_product_knowledge(
        AgentKnowledgeRequest(query="LIAN LI LANCOOL 216 支持多大水冷？")
    )

    assert response.sources
    assert response.trace_id == "trace-lancool"
    assert captured["sources_json"]
    assert captured["sources_json"][0]["filename"] == (
        "LIAN_LI_LANCOOL_216_case_manual.pdf"
    )
