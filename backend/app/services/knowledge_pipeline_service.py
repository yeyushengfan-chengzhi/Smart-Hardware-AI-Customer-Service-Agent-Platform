"""Idempotent batch pipeline for uploaded knowledge-base files."""

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.document_parser_service import (
    build_document_chunks,
    replace_document_chunks,
)
from app.services.knowledge_service import (
    ALLOWED_FILE_TYPES,
    BACKEND_DIR,
    RETRIEVABLE_EMBEDDING_STATUSES,
    UPLOAD_DIR,
    calculate_file_hash,
)
from app.services.vector_service import VectorService, vector_service


logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    filename: str
    file_hash: str
    document_id: int | None
    status: str
    chunk_count: int = 0
    embedding_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _relative_path(path: Path) -> str:
    return path.resolve().relative_to(BACKEND_DIR.resolve()).as_posix()


def _document_for_file(db: Session, path: Path, file_hash: str) -> tuple[KnowledgeDocument | None, bool]:
    relative_path = _relative_path(path)
    by_path = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.file_path == relative_path)
    )
    by_hash = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.file_hash == file_hash)
    )
    if by_hash is not None and (by_path is None or by_hash.id != by_path.id):
        if by_path is not None and by_path.file_hash is None:
            by_path.embedding_status = "failed"
            db.commit()
        return by_hash, True
    if by_path is not None:
        if by_path.file_hash is None:
            by_path.file_hash = file_hash
            by_path.embedding_status = by_path.embedding_status or "pending"
            db.commit()
        elif by_path.file_hash != file_hash:
            # The file at this registered path was replaced in place. Content
            # hash, not filename/path, controls incremental processing.
            by_path.file_hash = file_hash
            by_path.embedding_status = "pending"
            db.commit()
        return by_path, False

    document = KnowledgeDocument(
        filename=path.name,
        file_path=relative_path,
        file_type=path.suffix.lower().lstrip("."),
        file_hash=file_hash,
        status="active",
        embedding_status="pending",
    )
    db.add(document)
    try:
        db.commit()
        db.refresh(document)
        return document, False
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.file_hash == file_hash)
        )
        return existing, True


def _set_status(db_factory, document_id: int, status: str) -> None:
    """Update status with a fresh connection, retrying one stale-connection failure."""
    last_error: Exception | None = None
    for attempt in range(2):
        with db_factory() as db:
            try:
                document = db.get(KnowledgeDocument, document_id)
                if document is None:
                    raise RuntimeError("knowledge document does not exist")
                document.embedding_status = status
                db.commit()
                return
            except Exception as exc:
                db.rollback()
                last_error = exc
                logger.warning(
                    "Status update failed document_id=%d status=%s attempt=%d error=%s",
                    document_id,
                    status,
                    attempt + 1,
                    exc,
                )
    assert last_error is not None
    raise last_error


def process_file(
    db_factory, path: Path, vectors: VectorService = vector_service
) -> PipelineResult:
    file_hash = calculate_file_hash(path)
    document: KnowledgeDocument | None = None
    document_id: int | None = None
    try:
        with db_factory() as db:
            document, duplicate = _document_for_file(db, path, file_hash)
            if duplicate:
                return PipelineResult(
                    path.name,
                    file_hash,
                    document.id if document else None,
                    "duplicate",
                )
            if document is None:
                raise RuntimeError("unable to create document metadata")
            document_id = document.id
            filename = document.filename
            existing_chunks = db.scalar(
                select(func.count(KnowledgeChunk.id)).where(
                    KnowledgeChunk.document_id == document_id
                )
            ) or 0
            completed = (
                document.embedding_status in RETRIEVABLE_EMBEDDING_STATUSES
                and existing_chunks > 0
            )
            vector_metadata = {
                "filename": document.filename,
                "original_filename": document.original_filename,
                "product_name": document.product_name,
                "source_type": document.source_type,
                "embedding_status": "completed",
            }
            db.expunge(document)

        if completed:
            if document is not None and document.embedding_status == "success":
                _set_status(db_factory, document_id, "completed")
            try:
                embedding_count = vectors.count_documents(document_id)
                if hasattr(vectors, "update_document_metadata"):
                    vectors.update_document_metadata(document_id, vector_metadata)
            except Exception as exc:
                # A read-only statistics failure must not downgrade a document
                # whose DB status and chunks are already completed.
                logger.warning(
                    "Unable to count existing vectors document_id=%d error=%s",
                    document_id,
                    exc,
                )
                embedding_count = existing_chunks
            return PipelineResult(
                path.name,
                file_hash,
                document_id,
                "completed",
                existing_chunks,
                embedding_count,
            )

        _set_status(db_factory, document_id, "processing")
        logger.info(
            "Processing knowledge file filename=%s file_hash=%s document_id=%d",
            path.name,
            file_hash,
            document_id,
        )

        # Parsing is filesystem/CPU work. It runs on a detached model so no
        # MySQL connection remains checked out during long PDF extraction.
        parsed = build_document_chunks(document)
        if not parsed:
            raise RuntimeError("document contains no extractable text")

        # Persist chunks in a short, fresh transaction, then release MySQL
        # before the potentially long embedding and Chroma operations.
        with db_factory() as db:
            chunks = replace_document_chunks(db, document_id, parsed)
            stored_document = db.get(KnowledgeDocument, document_id)
            if stored_document is not None:
                stored_document.chunk_count = len(chunks)
                db.commit()
            payload = [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "document_id": document_id,
                    "filename": filename,
                    "original_filename": stored_document.original_filename if stored_document else "",
                    "product_name": stored_document.product_name if stored_document else "",
                    "source_type": stored_document.source_type if stored_document else "",
                    "embedding_status": "completed",
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title,
                }
                for chunk in chunks
            ]
        chunk_count = len(payload)
        embedding_count = vectors.add_documents(
            payload,
            document_id=document_id,
        )
        _set_status(db_factory, document_id, "completed")
        return PipelineResult(
            path.name, file_hash, document_id, "completed", chunk_count, embedding_count
        )
    except Exception as exc:
        if document_id is not None:
            try:
                _set_status(db_factory, document_id, "failed")
            except Exception:
                logger.exception(
                    "Unable to persist failed status document_id=%d", document_id
                )
        logger.exception("Knowledge pipeline failed for %s", path.name)
        return PipelineResult(
            path.name, file_hash, document_id, "failed", error=str(exc)
        )


def process_directory(
    db_factory, upload_dir: Path = UPLOAD_DIR, vectors: VectorService = vector_service
) -> list[PipelineResult]:
    """Process every supported file independently so one failure cannot stop the batch."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    results: list[PipelineResult] = []
    for path in sorted(upload_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower().lstrip(".") not in ALLOWED_FILE_TYPES:
            continue
        result = process_file(db_factory, path, vectors)
        results.append(result)
        logger.info(
            "Knowledge pipeline result filename=%s file_hash=%s document_id=%s "
            "status=%s chunk_count=%d embedding_count=%d error=%s",
            result.filename,
            result.file_hash,
            result.document_id,
            result.status,
            result.chunk_count,
            result.embedding_count,
            result.error or "",
        )
    return results
