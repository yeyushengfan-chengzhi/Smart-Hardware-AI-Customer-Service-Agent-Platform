"""Import Hermes-collected official manuals into the existing knowledge base."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.services.knowledge_service import (
    BACKEND_DIR,
    RETRIEVABLE_EMBEDDING_STATUSES,
    UPLOAD_DIR,
    calculate_file_hash,
)


PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_MANIFEST_PATH = PROJECT_DIR / "data_sources" / "download_manifest.json"
MIN_PDF_SIZE = 1024
SOURCE_TYPE = "official_manual_seed"
MANIFEST_UPDATING_MESSAGE = (
    "download_manifest.json may be updating, please retry later"
)
CATEGORY_KEYS = (
    "motherboard",
    "case",
    "gpu",
    "cpu_cooler",
    "aio_cooler",
    "psu",
)


class ManifestUpdatingError(ValueError):
    """Raised when a manifest cannot be decoded as one complete JSON snapshot."""


def read_manifest_records(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    missing_ok: bool = False,
) -> list[dict[str, Any]]:
    """Read one manifest snapshot without ever modifying the source file."""
    if not manifest_path.exists():
        if missing_ok:
            return []
        raise FileNotFoundError(f"manual seed manifest not found: {manifest_path}")
    try:
        payload = manifest_path.read_text(encoding="utf-8")
        records = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise ManifestUpdatingError(MANIFEST_UPDATING_MESSAGE) from exc
    if not isinstance(records, list):
        raise ValueError("manual seed manifest must contain a JSON array")
    return [record if isinstance(record, dict) else {} for record in records]


def _text(record: dict[str, Any], key: str) -> str:
    value = record.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _flag(record: dict[str, Any], key: str) -> bool:
    value = record.get(key, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return bool(value)


def _safe_part(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in value.strip()
    )
    return re.sub(r"_+", "_", cleaned).strip("._-")


def canonical_filename(record: dict[str, Any], file_hash: str) -> str:
    """Build a readable deterministic filename suitable for the upload directory."""
    parts = [
        _safe_part(_text(record, "vendor")),
        _safe_part(_text(record, "product_name")),
        _safe_part(_text(record, "product_category")),
        _safe_part(_text(record, "document_type")),
    ]
    stem = "_".join(part for part in parts if part) or f"official_manual_{file_hash[:12]}"
    return f"{stem[:220]}.pdf"


def _duplicate_document(
    db: Session,
    *,
    file_hash: str,
    file_url: str,
    support_url: str,
    source_url: str,
    original_filename: str,
) -> tuple[KnowledgeDocument | None, str]:
    checks = [
        ("file_hash", KnowledgeDocument.file_hash == file_hash),
    ]
    if file_url:
        checks.append(("file_url", KnowledgeDocument.file_url == file_url))
    if support_url:
        checks.append(("support_url", KnowledgeDocument.support_url == support_url))
    if source_url:
        checks.append(("source_url", KnowledgeDocument.source_url == source_url))
    if original_filename:
        checks.append(
            (
                "original_filename",
                func.lower(KnowledgeDocument.original_filename)
                == original_filename.casefold(),
            )
        )

    matches = list(
        db.scalars(select(KnowledgeDocument).where(or_(*(clause for _, clause in checks))))
    )
    for key, _ in checks:
        for document in matches:
            if key == "file_hash" and document.file_hash == file_hash:
                return document, key
            if key == "file_url" and document.file_url == file_url:
                return document, key
            if key == "support_url" and document.support_url == support_url:
                return document, key
            if key == "source_url" and document.source_url == source_url:
                return document, key
            if (
                key == "original_filename"
                and (document.original_filename or "").casefold()
                == original_filename.casefold()
            ):
                return document, key
    return None, ""


def _enrich_duplicate(document: KnowledgeDocument, record: dict[str, Any]) -> bool:
    """Fill missing seed metadata without overwriting existing knowledge metadata."""
    changed = False
    values = {
        "vendor": _text(record, "vendor"),
        "product_name": _text(record, "product_name"),
        "product_category": _text(record, "product_category"),
        "document_type": _text(record, "document_type"),
        "source_url": _text(record, "source_url"),
        "file_url": _text(record, "file_url"),
        "support_url": _text(record, "support_url"),
        "source_type": SOURCE_TYPE,
    }
    for field, value in values.items():
        if value and not getattr(document, field, ""):
            setattr(document, field, value)
            changed = True
    if _flag(record, "verified") and not document.verified:
        document.verified = True
        changed = True
    if _flag(record, "needs_review") and not document.needs_review:
        document.needs_review = True
        changed = True
    return changed


def _destination_path(
    upload_dir: Path, filename: str, source_hash: str
) -> tuple[Path, bool]:
    destination = upload_dir / filename
    if not destination.exists():
        return destination, False
    if destination.is_file() and calculate_file_hash(destination) == source_hash:
        return destination, True
    hashed_destination = destination.with_name(
        f"{destination.stem}_{source_hash[:12]}.pdf"
    )
    if not hashed_destination.exists():
        return hashed_destination, False
    if (
        hashed_destination.is_file()
        and calculate_file_hash(hashed_destination) == source_hash
    ):
        return hashed_destination, True
    full_hash_destination = destination.with_name(
        f"{destination.stem}_{source_hash}.pdf"
    )
    if not full_hash_destination.exists():
        return full_hash_destination, False
    if (
        full_hash_destination.is_file()
        and calculate_file_hash(full_hash_destination) == source_hash
    ):
        return full_hash_destination, True
    raise FileExistsError("all canonical manual destinations contain different data")


def _detail(
    index: int,
    record: dict[str, Any],
    status: str,
    reason: str,
    document_id: int | None = None,
) -> dict[str, Any]:
    return {
        "index": index,
        "status": status,
        "original_filename": _text(record, "original_filename"),
        "product_name": _text(record, "product_name"),
        "document_id": document_id,
        "reason": reason,
    }


def import_manual_seed_dataset(
    db: Session,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    upload_dir: Path = UPLOAD_DIR,
    backend_dir: Path = BACKEND_DIR,
) -> dict[str, Any]:
    """Import every manifest record, returning per-record idempotent statistics."""
    records = read_manifest_records(manifest_path)

    result: dict[str, Any] = {
        "total": len(records),
        "imported": 0,
        "skipped": 0,
        "failed": 0,
        "needs_review": 0,
        "details": [],
    }
    upload_dir.mkdir(parents=True, exist_ok=True)

    for index, raw_record in enumerate(records):
        record = raw_record if isinstance(raw_record, dict) else {}
        manifest_status = _text(record, "status").casefold()
        if manifest_status != "downloaded" or _flag(record, "needs_review"):
            result["skipped"] += 1
            if manifest_status == "needs_review" or _flag(record, "needs_review"):
                result["needs_review"] += 1
            result["details"].append(
                _detail(
                    index,
                    record,
                    "skipped",
                    f"manifest status is {manifest_status or 'missing'}",
                )
            )
            continue

        local_file_path = _text(record, "local_file_path")
        source_path = Path(local_file_path) if local_file_path else Path()
        if not local_file_path or not source_path.is_file():
            result["failed"] += 1
            result["details"].append(
                _detail(index, record, "failed", "local PDF file does not exist")
            )
            continue
        if source_path.stat().st_size < MIN_PDF_SIZE:
            result["failed"] += 1
            result["details"].append(
                _detail(
                    index,
                    record,
                    "failed",
                    f"file is smaller than {MIN_PDF_SIZE} bytes",
                )
            )
            continue
        if source_path.suffix.casefold() != ".pdf":
            result["failed"] += 1
            result["details"].append(
                _detail(index, record, "failed", "file extension is not .pdf")
            )
            continue
        with source_path.open("rb") as source:
            if source.read(5) != b"%PDF-":
                result["failed"] += 1
                result["details"].append(
                    _detail(index, record, "failed", "file header is not PDF")
                )
                continue

        file_hash = calculate_file_hash(source_path)
        original_filename = (
            Path(_text(record, "original_filename")).name or source_path.name
        )
        file_url = _text(record, "file_url")
        support_url = _text(record, "support_url")
        source_url = _text(record, "source_url")
        existing, duplicate_key = _duplicate_document(
            db,
            file_hash=file_hash,
            file_url=file_url,
            support_url=support_url,
            source_url=source_url,
            original_filename=original_filename,
        )
        if existing is not None:
            if _enrich_duplicate(existing, record):
                db.commit()
            result["skipped"] += 1
            result["details"].append(
                _detail(
                    index,
                    record,
                    "skipped",
                    f"duplicate {duplicate_key}",
                    existing.id,
                )
            )
            continue

        filename = canonical_filename(record, file_hash)
        destination, destination_matches = _destination_path(
            upload_dir, filename, file_hash
        )
        copied = False
        try:
            if not destination_matches:
                shutil.copy2(source_path, destination)
                copied = True
            relative_path = destination.resolve().relative_to(backend_dir.resolve()).as_posix()
            document = KnowledgeDocument(
                filename=destination.name,
                original_filename=original_filename,
                vendor=_text(record, "vendor"),
                product_name=_text(record, "product_name"),
                product_category=_text(record, "product_category"),
                document_type=_text(record, "document_type"),
                source_url=source_url,
                file_url=file_url,
                support_url=support_url,
                verified=_flag(record, "verified"),
                needs_review=_flag(record, "needs_review"),
                source_type=SOURCE_TYPE,
                version="1.0",
                file_path=relative_path,
                file_type="pdf",
                file_hash=file_hash,
                status="active",
                embedding_status="pending",
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            result["imported"] += 1
            result["details"].append(
                _detail(index, record, "imported", "imported", document.id)
            )
        except IntegrityError:
            db.rollback()
            if copied:
                destination.unlink(missing_ok=True)
            existing, duplicate_key = _duplicate_document(
                db,
                file_hash=file_hash,
                file_url=file_url,
                support_url=support_url,
                source_url=source_url,
                original_filename=original_filename,
            )
            result["skipped"] += 1
            result["details"].append(
                _detail(
                    index,
                    record,
                    "skipped",
                    f"duplicate {duplicate_key or 'record'}",
                    existing.id if existing else None,
                )
            )
        except Exception as exc:
            db.rollback()
            if copied:
                destination.unlink(missing_ok=True)
            result["failed"] += 1
            result["details"].append(
                _detail(index, record, "failed", f"import error: {exc}")
            )

    return result


def get_manual_seed_status(
    db: Session,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Return fast manifest and database counters without opening any PDF."""
    records = read_manifest_records(manifest_path, missing_ok=True)
    manifest_statuses = [_text(record, "status").casefold() for record in records]
    categories = {key: 0 for key in CATEGORY_KEYS}
    for record in records:
        category = _text(record, "product_category").casefold()
        if category in categories:
            categories[category] += 1

    document_stats = db.execute(
        select(
            func.count(KnowledgeDocument.id),
            func.coalesce(
                func.sum(
                    case(
                        (
                            KnowledgeDocument.embedding_status.in_(
                                RETRIEVABLE_EMBEDDING_STATUSES
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (KnowledgeDocument.embedding_status == "processing", 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (KnowledgeDocument.embedding_status == "failed", 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(KnowledgeDocument.chunk_count), 0),
        ).where(KnowledgeDocument.source_type == SOURCE_TYPE)
    ).one()

    return {
        "manifest_total": len(records),
        "manifest_downloaded": manifest_statuses.count("downloaded"),
        "manifest_needs_review": manifest_statuses.count("needs_review"),
        "manifest_failed": manifest_statuses.count("failed"),
        "imported_documents": int(document_stats[0] or 0),
        "completed_documents": int(document_stats[1] or 0),
        "processing_documents": int(document_stats[2] or 0),
        "failed_documents": int(document_stats[3] or 0),
        "total_chunks": int(document_stats[4] or 0),
        "categories": categories,
    }
