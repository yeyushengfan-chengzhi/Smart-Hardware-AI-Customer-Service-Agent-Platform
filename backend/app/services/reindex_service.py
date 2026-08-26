"""Safe, document-scoped parsing and vector reindexing."""

from typing import TypedDict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.document_parser_service import build_document_chunks, replace_document_chunks
from app.services.vector_service import VectorService, vector_service


class ReindexStats(TypedDict):
    document_id: int
    old_chunks: int
    new_chunks: int
    vectors: int


def _vector_payload(chunks: list[KnowledgeChunk], filename: str) -> list[dict]:
    return [
        {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "filename": filename,
            "page_number": chunk.page_number,
            "section_title": chunk.section_title,
        }
        for chunk in chunks
    ]


def reindex_document(
    db: Session, document_id: int, vectors: VectorService = vector_service
) -> ReindexStats:
    """Atomically replace one document's DB chunks and best-effort restore vectors on failure."""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document does not exist")

    old_chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index)
        ).all()
    )
    old_payload = _vector_payload(old_chunks, document.filename)
    parsed = build_document_chunks(document)
    if not parsed:
        raise HTTPException(status_code=422, detail="document contains no extractable text")

    try:
        new_models = replace_document_chunks(db, document_id, parsed, commit=False)
        vector_count = vectors.add_documents(
            _vector_payload(new_models, document.filename), document_id=document_id
        )
        db.commit()
    except Exception:
        db.rollback()
        if old_payload:
            vectors.add_documents(old_payload, document_id=document_id)
        raise

    return {
        "document_id": document_id,
        "old_chunks": len(old_chunks),
        "new_chunks": len(new_models),
        "vectors": vector_count,
    }
