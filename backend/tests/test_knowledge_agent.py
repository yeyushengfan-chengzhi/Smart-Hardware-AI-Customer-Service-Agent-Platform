import pytest
from fastapi import HTTPException

from app.agents.knowledge_agent import KnowledgeAgent
from app.routers import agent as agent_router
from app.schemas import AgentKnowledgeRequest


class FakeRAGService:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k):
        self.calls.append((query, top_k))
        return [
            {
                "filename": "b850.pdf",
                "page_number": 1,
                "section_title": "CPU 支持",
                "content": "B850 CPU support content",
            }
        ]


class FakeLLMService:
    def __init__(self):
        self.calls = []

    def generate_answer(self, query, contexts):
        self.calls.append((query, contexts))
        if "DDR5" in query:
            return "根据产品说明书，该主板包含 DDR5 内存支持信息。"
        return "根据产品说明书，相关支持信息如下。"


@pytest.mark.parametrize("query", ["B850支持什么CPU", "B850主板支持DDR5吗"])
def test_product_query_returns_answer_and_sources(query):
    rag = FakeRAGService()
    llm = FakeLLMService()
    result = KnowledgeAgent(rag, llm).answer(query, top_k=3)

    assert result["answer"]
    assert result["sources"]
    assert rag.calls[0][1] == 3
    assert rag.calls[0][0].startswith(query)
    assert llm.calls[0][0] == query


def test_ddr5_query_is_enhanced_for_retrieval_and_keeps_original_llm_question():
    query = "B850主板支持DDR5吗"
    rag = FakeRAGService()
    llm = FakeLLMService()

    result = KnowledgeAgent(rag, llm).answer(query, top_k=3)
    retrieval_query = rag.calls[0][0]

    assert all(term in retrieval_query for term in ("B850", "DDR5", "内存", "Memory", "DIMM", "规格", "兼容"))
    assert "DDR5" in result["answer"]
    assert result["sources"]
    assert llm.calls[0][0] == query


def test_cpu_query_is_enhanced_and_still_returns_sources():
    query = "B850支持什么CPU"
    rag = FakeRAGService()
    result = KnowledgeAgent(rag, FakeLLMService()).answer(query)

    assert all(term in rag.calls[0][0] for term in ("B850", "CPU", "处理器", "规格", "兼容"))
    assert result["answer"]
    assert result["sources"]


def test_cooling_query_is_enhanced_and_keeps_manual_source():
    query = "LIAN LI LANCOOL 216 支持多大水冷？"
    rag = FakeRAGService()
    result = KnowledgeAgent(rag, FakeLLMService()).answer(query)

    assert all(term in rag.calls[0][0] for term in ("LANCOOL 216", "Radiator", "Water Cooling", "360"))
    assert result["sources"]


def test_knowledge_endpoint_accepts_product_query(monkeypatch):
    monkeypatch.setattr(
        agent_router.knowledge_agent,
        "answer",
        lambda query, top_k: {
            "query": query,
            "answer": "B850 产品知识回答",
            "sources": [{"filename": "b850.pdf", "page_number": 1, "section_title": "规格"}],
        },
    )

    response = agent_router.answer_product_knowledge(
        AgentKnowledgeRequest(query="B850支持什么CPU", top_k=3)
    )

    assert response.answer
    assert response.sources


def test_diagnosis_query_is_rejected_by_knowledge_endpoint(monkeypatch):
    called = False

    def should_not_run(query, top_k):
        nonlocal called
        called = True

    monkeypatch.setattr(agent_router.knowledge_agent, "answer", should_not_run)

    with pytest.raises(HTTPException) as exc_info:
        agent_router.answer_product_knowledge(
            AgentKnowledgeRequest(query="我的主板开机没有显示怎么办")
        )

    assert exc_info.value.status_code == 422
    assert called is False


def test_knowledge_endpoint_is_exposed_in_openapi():
    from app.main import app

    assert "/api/agent/knowledge" in app.openapi()["paths"]
