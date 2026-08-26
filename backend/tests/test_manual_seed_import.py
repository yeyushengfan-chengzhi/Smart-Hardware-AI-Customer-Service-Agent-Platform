import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.main import app
from app.models.knowledge_document import KnowledgeDocument
from app.services.manual_seed_import_service import (
    MANIFEST_UPDATING_MESSAGE,
    ManifestUpdatingError,
    get_manual_seed_status,
    import_manual_seed_dataset,
)
from app.database import Base


def _record(path, **overrides):
    record = {
        "vendor": "ASUS",
        "product_name": "TUF GAMING B850M-PLUS WIFI",
        "product_category": "motherboard",
        "document_type": "manual",
        "local_file_path": str(path),
        "source_url": "",
        "file_url": "https://vendor.example/manual.pdf",
        "support_url": "https://vendor.example/support",
        "original_filename": "manual.pdf",
        "status": "downloaded",
        "verified": True,
        "needs_review": False,
    }
    record.update(overrides)
    return record


def test_manual_seed_import_validates_records_and_is_idempotent(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    backend_dir = tmp_path / "backend"
    upload_dir = backend_dir / "uploads" / "knowledge"
    source_dir = tmp_path / "manuals"
    source_dir.mkdir()

    valid = source_dir / "manual.pdf"
    valid.write_bytes(b"%PDF-1.7\n" + b"valid manual content " * 100)
    tiny = source_dir / "tiny.pdf"
    tiny.write_bytes(b"%PDF-1.7\n")
    html = source_dir / "error.pdf"
    html.write_bytes(b"<html>not a pdf</html>" * 100)
    manifest = tmp_path / "download_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                _record(valid),
                _record("", status="needs_review", original_filename="pending.pdf"),
                _record(tiny, file_url="https://vendor.example/tiny.pdf"),
                _record(html, file_url="https://vendor.example/error.pdf"),
                _record(
                    source_dir / "missing.pdf",
                    file_url="https://vendor.example/missing.pdf",
                ),
            ]
        ),
        encoding="utf-8",
    )

    with Session(engine) as db:
        first = import_manual_seed_dataset(
            db,
            manifest_path=manifest,
            upload_dir=upload_dir,
            backend_dir=backend_dir,
        )
        assert first["total"] == 5
        assert first["imported"] == 1
        assert first["skipped"] == 1
        assert first["failed"] == 3
        assert first["needs_review"] == 1

        document = db.scalar(select(KnowledgeDocument))
        assert document is not None
        assert document.vendor == "ASUS"
        assert document.product_name == "TUF GAMING B850M-PLUS WIFI"
        assert document.document_type == "manual"
        assert document.source_url == ""
        assert document.file_url == "https://vendor.example/manual.pdf"
        assert document.support_url == "https://vendor.example/support"
        assert document.verified is True
        assert document.needs_review is False
        assert document.source_type == "official_manual_seed"
        assert document.original_filename == "manual.pdf"
        assert (backend_dir / document.file_path).read_bytes() == valid.read_bytes()
        assert valid.exists()

        second = import_manual_seed_dataset(
            db,
            manifest_path=manifest,
            upload_dir=upload_dir,
            backend_dir=backend_dir,
        )
        assert second["imported"] == 0
        assert second["skipped"] == 2
        assert second["failed"] == 3
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1
        assert len(list(upload_dir.iterdir())) == 1


def test_manual_seed_import_endpoint_is_exposed():
    operation = app.openapi()["paths"]["/api/knowledge/import-manual-seeds"]["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("ManualSeedImportResponse")
    status_operation = app.openapi()["paths"]["/api/knowledge/manual-seed-status"]["get"]
    status_schema = status_operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert status_schema["$ref"].endswith("ManualSeedStatusResponse")


def test_manual_seed_status_uses_manifest_and_official_documents_only(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    manifest = tmp_path / "download_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                _record("", status="downloaded", product_category="case"),
                _record("", status="needs_review", product_category="aio_cooler"),
                _record("", status="failed", product_category="gpu"),
            ]
        ),
        encoding="utf-8",
    )
    with Session(engine) as db:
        db.add_all(
            [
                KnowledgeDocument(
                    filename="one.pdf", original_filename="one.pdf",
                    file_path="uploads/knowledge/one.pdf", file_type="pdf",
                    file_hash="1" * 64, source_type="official_manual_seed",
                    embedding_status="completed", chunk_count=12,
                ),
                KnowledgeDocument(
                    filename="two.pdf", original_filename="two.pdf",
                    file_path="uploads/knowledge/two.pdf", file_type="pdf",
                    file_hash="2" * 64, source_type="official_manual_seed",
                    embedding_status="processing", chunk_count=3,
                ),
                KnowledgeDocument(
                    filename="other.pdf", original_filename="other.pdf",
                    file_path="uploads/knowledge/other.pdf", file_type="pdf",
                    file_hash="3" * 64, source_type="upload",
                    embedding_status="completed", chunk_count=99,
                ),
            ]
        )
        db.commit()
        result = get_manual_seed_status(db, manifest_path=manifest)
    assert result["manifest_total"] == 3
    assert result["manifest_downloaded"] == 1
    assert result["manifest_needs_review"] == 1
    assert result["manifest_failed"] == 1
    assert result["imported_documents"] == 2
    assert result["completed_documents"] == 1
    assert result["processing_documents"] == 1
    assert result["total_chunks"] == 15
    assert result["categories"]["case"] == 1
    assert result["categories"]["aio_cooler"] == 1


def test_manual_seed_status_returns_empty_when_manifest_is_missing(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    with Session(engine) as db:
        result = get_manual_seed_status(
            db,
            manifest_path=tmp_path / "missing-manifest.json",
        )
    assert result["manifest_total"] == 0
    assert result["categories"] == {
        "motherboard": 0,
        "case": 0,
        "gpu": 0,
        "cpu_cooler": 0,
        "aio_cooler": 0,
        "psu": 0,
    }


def test_manifest_parse_failure_has_retry_message(tmp_path):
    manifest = tmp_path / "download_manifest.json"
    manifest.write_text('[{"status": "downloaded"', encoding="utf-8")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    with Session(engine) as db:
        with pytest.raises(ManifestUpdatingError, match=MANIFEST_UPDATING_MESSAGE):
            get_manual_seed_status(db, manifest_path=manifest)


def test_manual_seed_import_deduplicates_by_support_url(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    backend_dir = tmp_path / "backend"
    upload_dir = backend_dir / "uploads" / "knowledge"
    source_dir = tmp_path / "manuals"
    source_dir.mkdir()
    first_pdf = source_dir / "first.pdf"
    second_pdf = source_dir / "second.pdf"
    first_pdf.write_bytes(b"%PDF-1.7\n" + b"first content " * 100)
    second_pdf.write_bytes(b"%PDF-1.7\n" + b"second content " * 100)
    shared_support_url = "https://vendor.example/shared-support"
    manifest = tmp_path / "download_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                _record(
                    first_pdf,
                    file_url="https://vendor.example/first.pdf",
                    support_url=shared_support_url,
                    original_filename="first.pdf",
                ),
                _record(
                    second_pdf,
                    file_url="https://vendor.example/second.pdf",
                    support_url=shared_support_url,
                    original_filename="second.pdf",
                ),
            ]
        ),
        encoding="utf-8",
    )
    with Session(engine) as db:
        result = import_manual_seed_dataset(
            db,
            manifest_path=manifest,
            upload_dir=upload_dir,
            backend_dir=backend_dir,
        )
        assert result["imported"] == 1
        assert result["skipped"] == 1
        assert "support_url" in result["details"][1]["reason"]
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1
