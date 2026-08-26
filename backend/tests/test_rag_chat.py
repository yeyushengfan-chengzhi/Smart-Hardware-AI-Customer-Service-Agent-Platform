from app.routers import rag as rag_router
from app.schemas import RAGChatRequest


def test_chat_calls_rag_and_llm_and_returns_sources(monkeypatch):
    contexts = [{
        "chunk_id": 42,
        "document_id": 2,
        "filename": "manual.pdf",
        "page_number": 51,
        "section_title": "简易侦错 LED 灯",
        "content": "白色 LED 表示 GPU 无法检测或故障。",
        "score": 0.9,
        "semantic_score": 0.85,
        "keyword_score": 1.0,
    }]
    calls = {}

    def fake_search(query, top_k):
        calls["search"] = (query, top_k)
        return contexts

    def fake_generate(query, supplied_contexts):
        calls["llm"] = (query, supplied_contexts)
        return "您好，建议按以下步骤排查：\n1. 检查显卡连接。"

    monkeypatch.setattr(rag_router.rag_service, "search", fake_search)
    monkeypatch.setattr(rag_router.llm_service, "generate_answer", fake_generate)

    response = rag_router.chat_with_knowledge(RAGChatRequest(query="显卡无法检测怎么办"))

    assert calls["search"] == ("显卡无法检测怎么办", 3)
    assert calls["llm"] == ("显卡无法检测怎么办", contexts)
    assert response.answer.startswith("您好")
    assert response.sources[0].filename == "manual.pdf"
    assert response.sources[0].page_number == 51
    assert response.sources[0].section_title == "简易侦错 LED 灯"
