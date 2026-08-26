from app.routers import knowledge as knowledge_router
from app.schemas import KnowledgeSearchRequest, RAGSearchResponse


def test_rag_response_exposes_scores_and_source_metadata():
    response = RAGSearchResponse(
        query="主板白色故障灯一直亮",
        count=1,
        results=[
            {
                "content": "白色表示 GPU 无法检测或故障。",
                "score": 0.82,
                "semantic_score": 0.78,
                "keyword_score": 0.98,
                "filename": "manual.pdf",
                "page_number": 51,
                "section_title": "简易侦错 LED 灯",
                "chunk_id": 42,
                "document_id": 2,
            }
        ],
    )
    assert response.count == len(response.results)
    assert response.results[0].page_number == 51


def test_knowledge_center_search_uses_product_aware_rag(monkeypatch):
    monkeypatch.setattr(
        knowledge_router.rag_service,
        "search",
        lambda query, top_k: [{
            "chunk_id": 23755,
            "document_id": 35,
            "filename": "LIAN_LI_LANCOOL_216_case_manual.pdf",
            "page_number": 1,
            "section_title": "Case Components",
            "content": "Supporting 360 mm radiator x 1",
            "score": 0.72,
            "semantic_score": 0.65,
            "keyword_score": 0.8,
        }],
    )

    response = knowledge_router.admin_search_test(
        KnowledgeSearchRequest(query="LANCOOL 216 radiator", top_k=5),
        db=None,
    )

    assert response.results
    assert response.results[0].filename == (
        "LIAN_LI_LANCOOL_216_case_manual.pdf"
    )
    assert response.results[0].score == 0.72
