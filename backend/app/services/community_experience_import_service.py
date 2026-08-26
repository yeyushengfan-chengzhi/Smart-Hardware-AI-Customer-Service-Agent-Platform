"""Import the local community-experience seed as one knowledge document."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.services.knowledge_service import (
    BACKEND_DIR,
    UPLOAD_DIR,
    calculate_file_hash,
)
from app.services.source_policy import COMMUNITY_EXPERIENCE_SOURCE_TYPE


PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_DATA_DIR = PROJECT_DIR / "data_sources" / "community_experience"
DEFAULT_SEED_PATH = DEFAULT_DATA_DIR / "community_experience_seed.md"
DEFAULT_MANIFEST_PATH = DEFAULT_DATA_DIR / "community_experience_manifest.json"
DOCUMENT_TYPE = "community_experience_seed"
PRODUCT_NAME = "DIY 装机社区经验种子数据集"


def _detail(
    status: str,
    reason: str,
    document_id: int | None = None,
) -> dict[str, Any]:
    return {
        "index": 0,
        "status": status,
        "original_filename": DEFAULT_SEED_PATH.name,
        "product_name": PRODUCT_NAME,
        "document_id": document_id,
        "reason": reason,
    }


def read_community_manifest(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> dict:
    """Read and minimally validate the Hermes manifest without modifying it."""
    if not manifest_path.is_file():
        raise FileNotFoundError(f"community manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("community manifest must contain a JSON object")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("community manifest entries must be a JSON array")
    return payload


def _destination_path(upload_dir: Path, seed_path: Path, file_hash: str) -> Path:
    destination = upload_dir / seed_path.name
    if not destination.exists():
        return destination
    if destination.is_file() and calculate_file_hash(destination) == file_hash:
        return destination
    return upload_dir / f"{seed_path.stem}_{file_hash[:12]}{seed_path.suffix}"


def import_community_experience_seed(
    db: Session,
    *,
    seed_path: Path = DEFAULT_SEED_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    upload_dir: Path = UPLOAD_DIR,
    backend_dir: Path = BACKEND_DIR,
) -> dict[str, Any]:
    """Import one immutable seed file with file-hash idempotency."""
    result: dict[str, Any] = {
        "total": 1,
        "imported": 0,
        "skipped": 0,
        "failed": 0,
        "details": [],
    }
    try:
        read_community_manifest(manifest_path)
        if not seed_path.is_file():
            raise FileNotFoundError(f"community seed not found: {seed_path}")
        file_hash = calculate_file_hash(seed_path)
        existing = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.file_hash == file_hash
            )
        )
        if existing is not None:
            result["skipped"] = 1
            result["details"].append(
                _detail("skipped", "duplicate file_hash", existing.id)
            )
            return result

        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = _destination_path(upload_dir, seed_path, file_hash)
        if not destination.exists():
            shutil.copyfile(seed_path, destination)
        relative_path = destination.resolve().relative_to(
            backend_dir.resolve()
        ).as_posix()
        document = KnowledgeDocument(
            filename=destination.name,
            original_filename=seed_path.name,
            product_name=PRODUCT_NAME,
            product_category=COMMUNITY_EXPERIENCE_SOURCE_TYPE,
            document_type=DOCUMENT_TYPE,
            verified=False,
            needs_review=False,
            source_type=COMMUNITY_EXPERIENCE_SOURCE_TYPE,
            file_path=relative_path,
            file_type="md",
            file_hash=file_hash,
            status="active",
            embedding_status="pending",
        )
        db.add(document)
        try:
            db.commit()
            db.refresh(document)
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.file_hash == file_hash
                )
            )
            if existing is None:
                raise
            result["skipped"] = 1
            result["details"].append(
                _detail("skipped", "duplicate file_hash", existing.id)
            )
            return result

        result["imported"] = 1
        result["details"].append(
            _detail("imported", "community seed imported", document.id)
        )
    except Exception as exc:
        db.rollback()
        result["failed"] = 1
        result["details"].append(_detail("failed", str(exc)))
    return result
