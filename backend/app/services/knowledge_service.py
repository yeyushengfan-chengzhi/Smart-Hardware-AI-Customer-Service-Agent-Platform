"""Knowledge base file storage and metadata operations."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument


ALLOWED_FILE_TYPES = {"pdf", "txt", "md"}
RETRIEVABLE_EMBEDDING_STATUSES = ("completed", "success")
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads" / "knowledge"


@dataclass(frozen=True)
class UploadResult:
    document: KnowledgeDocument
    duplicate: bool = False


def calculate_file_hash(file_path: Path) -> str:
    """Return the SHA-256 digest without loading the whole file into memory."""
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def find_document_by_hash(db: Session, file_hash: str) -> KnowledgeDocument | None:
    """Find a digest match, lazily hashing pre-Milestone-3.6 database rows."""
    existing = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.file_hash == file_hash)
    )
    if existing is not None:
        return existing

    legacy_documents = db.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.file_hash.is_(None))
    ).all()
    upload_root = UPLOAD_DIR.resolve()
    for document in legacy_documents:
        candidate = (BACKEND_DIR / document.file_path).resolve()
        if not candidate.is_relative_to(upload_root) or not candidate.is_file():
            continue
        if calculate_file_hash(candidate) == file_hash:
            document.file_hash = file_hash
            document.status = document.status or "pending"
            db.commit()
            db.refresh(document)
            return document
    return None


def _validated_filename(upload: UploadFile) -> tuple[str, str]:
    """Return a safe filename and its validated lowercase extension."""
    filename = Path(upload.filename or "").name
    if not filename or filename in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filename is required",
        )

    file_type = Path(filename).suffix.lower().lstrip(".")
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="only pdf, txt and md files are supported",
        )
    return filename, file_type


def save_knowledge_document(
    db: Session, upload: UploadFile, *, product_name: str = "",
    product_category: str = "", version: str = "1.0",
) -> UploadResult:
    """Persist an uploaded file and its database metadata."""
    filename, file_type = _validated_filename(upload)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}_{filename}"
    absolute_path = UPLOAD_DIR / stored_name
    relative_path = (Path("uploads") / "knowledge" / stored_name).as_posix()

    try:
        with absolute_path.open("wb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                destination.write(chunk)

        file_hash = calculate_file_hash(absolute_path)
        existing = find_document_by_hash(db, file_hash)
        if existing is not None:
            absolute_path.unlink(missing_ok=True)
            return UploadResult(document=existing, duplicate=True)

        document = KnowledgeDocument(
            filename=filename,
            original_filename=filename,
            product_name=product_name.strip(),
            product_category=product_category.strip(),
            version=version.strip() or "1.0",
            file_path=relative_path,
            file_type=file_type,
            file_hash=file_hash,
            status="active",
            embedding_status="pending",
        )
        if document.product_name:
            for previous in db.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.product_name == document.product_name,
                    KnowledgeDocument.status == "active",
                )
            ).all():
                previous.status = "inactive"
        db.add(document)
        db.commit()
        db.refresh(document)
        return UploadResult(document=document)
    except Exception:
        db.rollback()
        absolute_path.unlink(missing_ok=True)
        raise
    finally:
        upload.file.close()


def list_knowledge_documents(db: Session) -> list[KnowledgeDocument]:
    """Return all uploaded knowledge documents, newest first."""
    return list(
        db.scalars(
            select(KnowledgeDocument).order_by(
                KnowledgeDocument.created_time.desc(),
                KnowledgeDocument.id.desc(),
            )
        ).all()
    )
