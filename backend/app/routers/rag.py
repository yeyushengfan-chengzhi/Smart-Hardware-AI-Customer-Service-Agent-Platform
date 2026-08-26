"""RAG semantic retrieval endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    RAGChatRequest,
    RAGChatResponse,
    RAGChatSource,
    RAGSearchRequest,
    RAGSearchResponse,
)
from app.services.llm_service import LLMServiceError, llm_service
from app.services.rag_service import rag_service
from app.services.source_policy import apply_source_policy, source_label


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RAGSearchResponse)
def search_knowledge(payload: RAGSearchRequest) -> RAGSearchResponse:
    """Return knowledge chunks semantically related to the user's question."""
    results = rag_service.search(query=payload.query, top_k=payload.top_k)
    return RAGSearchResponse(
        query=payload.query,
        count=len(results),
        results=results,
    )


@router.post("/chat", response_model=RAGChatResponse)
def chat_with_knowledge(payload: RAGChatRequest) -> RAGChatResponse:
    """Retrieve relevant chunks and generate a grounded customer-service answer."""
    contexts = rag_service.search(query=payload.query, top_k=3)
    try:
        answer = llm_service.generate_answer(payload.query, contexts)
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    answer = apply_source_policy(answer, contexts)
    sources = [
        RAGChatSource(
            filename=context["filename"],
            page_number=context["page_number"],
            section_title=context["section_title"],
            source_type=context.get("source_type", ""),
            source_label=source_label(context.get("source_type", "")),
        )
        for context in contexts
    ]
    return RAGChatResponse(query=payload.query, answer=answer, sources=sources)
