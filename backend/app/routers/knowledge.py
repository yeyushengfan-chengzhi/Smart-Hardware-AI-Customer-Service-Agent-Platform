"""Knowledge base file management endpoints."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge_document import KnowledgeDocument
from app.schemas import (
    EmbeddingTestRequest,
    EmbeddingTestResponse,
    KnowledgeChunkResponse,
    KnowledgeAdminChunkResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentStatusRequest,
    KnowledgeUploadResponse,
    ManualSeedImportResponse,
    ManualSeedStatusResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchTestResponse,
    KnowledgeVectorStatusResponse,
    ParseDocumentResponse,
    VectorizeDocumentResponse,
)
from app.security import require_admin
from app.services.document_parser_service import list_document_chunks, parse_document
from app.services.embedding_service import embedding_service
from app.services.vector_service import vector_service
from app.services.knowledge_service import (
    list_knowledge_documents,
    save_knowledge_document,
)
from app.services.manual_seed_import_service import (
    ManifestUpdatingError,
    get_manual_seed_status,
    import_manual_seed_dataset,
)
from app.services.rag_service import rag_service
from app.services.source_policy import source_label
from app.models.knowledge_chunk import KnowledgeChunk


router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(require_admin)])


@router.post("/import-manual-seeds", response_model=ManualSeedImportResponse)
def import_manual_seeds(db: Session = Depends(get_db)) -> ManualSeedImportResponse:
    """Import the local official-manual manifest without downloading source files."""
    try:
        result = import_manual_seed_dataset(db)
    except ManifestUpdatingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ManualSeedImportResponse.model_validate(result)


@router.get("/manual-seed-status", response_model=ManualSeedStatusResponse)
def manual_seed_status(db: Session = Depends(get_db)) -> ManualSeedStatusResponse:
    """Summarize the official-manual expansion pipeline without scanning PDFs."""
    try:
        result = get_manual_seed_status(db)
    except ManifestUpdatingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ManualSeedStatusResponse.model_validate(result)


@router.post(
    "/upload",
    response_model=KnowledgeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_knowledge_document(
    file: UploadFile = File(...),
    product_name: str = Form(default=""),
    product_category: str = Form(default=""),
    version: str = Form(default="1.0"),
    db: Session = Depends(get_db),
) -> KnowledgeUploadResponse:
    """Upload one supported knowledge base file."""
    result = save_knowledge_document(
        db, file, product_name=product_name,
        product_category=product_category, version=version,
    )
    document = result.document
    return KnowledgeUploadResponse(
        id=document.id,
        document_id=document.id,
        filename=document.filename,
        hash=document.file_hash or "",
        status="duplicate" if result.duplicate else document.embedding_status,
        message=("duplicate document detected" if result.duplicate else "upload success"),
    )


@router.get("/list", response_model=list[KnowledgeDocumentResponse])
def get_knowledge_documents(
    db: Session = Depends(get_db),
) -> list[KnowledgeDocumentResponse]:
    """List all files registered in the knowledge base."""
    return [
        KnowledgeDocumentResponse.model_validate(document)
        for document in list_knowledge_documents(db)
    ]


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
def list_admin_documents(
    product_name: str | None = None,
    source_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    embedding_status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[KnowledgeDocument]:
    statement = select(KnowledgeDocument)
    if product_name:
        statement = statement.where(KnowledgeDocument.product_name.contains(product_name))
    if source_type:
        statement = statement.where(KnowledgeDocument.source_type == source_type)
    if status_filter:
        statement = statement.where(KnowledgeDocument.status == status_filter)
    if embedding_status:
        statement = statement.where(KnowledgeDocument.embedding_status == embedding_status)
    return list(db.scalars(statement.order_by(
        KnowledgeDocument.created_time.desc(), KnowledgeDocument.id.desc()
    ).limit(limit)).all())


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentResponse)
def get_admin_document(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document does not exist")
    return document


@router.patch("/documents/{document_id}/status", response_model=KnowledgeDocumentResponse)
def update_admin_document_status(
    document_id: int, payload: KnowledgeDocumentStatusRequest,
    db: Session = Depends(get_db),
) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document does not exist")
    document.status = payload.status
    db.commit()
    db.refresh(document)
    return document


@router.post("/embed/test", response_model=EmbeddingTestResponse)
def test_embedding(payload: EmbeddingTestRequest) -> EmbeddingTestResponse:
    """Encode a text batch and report its output shape."""
    vectors = embedding_service.encode(payload.texts)
    return EmbeddingTestResponse(
        count=len(vectors),
        dimension=len(vectors[0]) if vectors else 0,
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(payload: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    """Search the most semantically similar vectorized chunks."""
    return KnowledgeSearchResponse(
        results=vector_service.search(payload.query, payload.top_k)
    )


@router.post(
    "/{document_id}/vectorize",
    response_model=VectorizeDocumentResponse,
)
def vectorize_knowledge_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> VectorizeDocumentResponse:
    """Embed all parsed chunks for a document and persist them in Chroma."""
    chunks = list_document_chunks(db, document_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="document has no chunks; parse it first",
        )
    document = db.get(KnowledgeDocument, document_id)
    if document:
        document.embedding_status = "processing"
        document.chunk_count = len(chunks)
        db.commit()
    try:
        vector_count = vector_service.add_documents([
            {
                "id": chunk.id,
                "content": chunk.content,
                "document_id": document_id,
                "filename": document.filename if document else "",
                "original_filename": document.original_filename if document else "",
                "product_name": document.product_name if document else "",
                "source_type": document.source_type if document else "",
                "embedding_status": "completed",
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
            }
            for chunk in chunks
        ], document_id=document_id)
        if document:
            document.embedding_status = "completed"
            db.commit()
    except Exception:
        if document:
            document.embedding_status = "failed"
            db.commit()
        raise
    return VectorizeDocumentResponse(
        message="vectorize success",
        vectors=vector_count,
    )


@router.post("/{document_id}/parse", response_model=ParseDocumentResponse)
def parse_knowledge_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> ParseDocumentResponse:
    """Parse an uploaded document and persist its ordered text chunks."""
    chunk_count = parse_document(db, document_id)
    document = db.get(KnowledgeDocument, document_id)
    if document is not None:
        document.chunk_count = chunk_count
        document.embedding_status = "pending"
        db.commit()
    return ParseDocumentResponse(message="parse success", chunks=chunk_count)


@router.get("/documents/{document_id}/chunks", response_model=list[KnowledgeAdminChunkResponse])
@router.get("/{document_id}/chunks", response_model=list[KnowledgeAdminChunkResponse], include_in_schema=False)
def get_knowledge_document_chunks(
    document_id: int,
    db: Session = Depends(get_db),
) -> list[KnowledgeChunkResponse]:
    """Return all parsed text chunks for one document."""
    return [KnowledgeAdminChunkResponse(
        chunk_id=chunk.id, content=chunk.content, page_number=chunk.page_number,
        section_title=chunk.section_title,
    ) for chunk in list_document_chunks(db, document_id)]


@router.get(
    "/documents/{document_id}/vector-status",
    response_model=KnowledgeVectorStatusResponse,
)
def get_knowledge_document_vector_status(
    document_id: int,
    db: Session = Depends(get_db),
) -> KnowledgeVectorStatusResponse:
    """Inspect DB/Chroma consistency for one knowledge document."""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document does not exist")
    db_chunk_count = int(db.scalar(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.document_id == document_id
        )
    ) or 0)
    vector_status = vector_service.inspect_document(document_id)
    return KnowledgeVectorStatusResponse(
        document_id=document_id,
        filename=document.filename,
        status=document.status,
        embedding_status=document.embedding_status,
        db_chunk_count=db_chunk_count,
        vector_count=vector_status["vector_count"],
        metadata_samples=vector_status["metadatas"],
    )


@router.post("/search_test", response_model=KnowledgeSearchTestResponse)
def admin_search_test(
    payload: KnowledgeSearchRequest, db: Session = Depends(get_db)
) -> KnowledgeSearchTestResponse:
    return KnowledgeSearchTestResponse(results=[
        {
            "content": item["content"], "filename": item["filename"],
            "page_number": item["page_number"], "section_title": item["section_title"],
            "score": item["score"],
            "source_type": item.get("source_type", ""),
            "source_label": item.get("source_label") or source_label(
                item.get("source_type", "")
            ),
        }
        for item in rag_service.search(payload.query, payload.top_k)
    ])
