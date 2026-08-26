from io import BytesIO

from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models.knowledge_document import KnowledgeDocument
from app.services import knowledge_service


def test_upload_deduplicates_by_content_before_creating_document(tmp_path, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    monkeypatch.setattr(knowledge_service, "UPLOAD_DIR", tmp_path)

    with Session(engine) as db:
        first = knowledge_service.save_knowledge_document(
            db, UploadFile(filename="ASUS.pdf", file=BytesIO(b"same pdf bytes"))
        )
        duplicate = knowledge_service.save_knowledge_document(
            db, UploadFile(filename="MSI_copy.pdf", file=BytesIO(b"same pdf bytes"))
        )

        assert first.duplicate is False
        assert duplicate.duplicate is True
        assert duplicate.document.id == first.document.id
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1
        assert len(list(tmp_path.iterdir())) == 1


def test_upload_matches_legacy_document_without_hash(tmp_path, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    upload_dir = tmp_path / "uploads" / "knowledge"
    upload_dir.mkdir(parents=True)
    (upload_dir / "legacy.pdf").write_bytes(b"legacy bytes")
    monkeypatch.setattr(knowledge_service, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(knowledge_service, "UPLOAD_DIR", upload_dir)

    with Session(engine) as db:
        legacy = KnowledgeDocument(
            filename="legacy.pdf",
            file_path="uploads/knowledge/legacy.pdf",
            file_type="pdf",
        )
        db.add(legacy)
        db.commit()
        result = knowledge_service.save_knowledge_document(
            db, UploadFile(filename="renamed.pdf", file=BytesIO(b"legacy bytes"))
        )

        assert result.duplicate is True
        assert result.document.id == legacy.id
        assert result.document.file_hash is not None
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1


def test_new_product_version_deactivates_previous_version(tmp_path, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    monkeypatch.setattr(knowledge_service, "UPLOAD_DIR", tmp_path)

    with Session(engine) as db:
        first = knowledge_service.save_knowledge_document(
            db, UploadFile(filename="manual_v1.pdf", file=BytesIO(b"version one")),
            product_name="B850", product_category="motherboard", version="1.0",
        ).document
        second = knowledge_service.save_knowledge_document(
            db, UploadFile(filename="manual_v2.pdf", file=BytesIO(b"version two")),
            product_name="B850", product_category="motherboard", version="2.0",
        ).document

        db.refresh(first)
        assert first.status == "inactive"
        assert second.status == "active"
        assert second.version == "2.0"
