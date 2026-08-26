import json

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models.knowledge_document import KnowledgeDocument
from app.services.community_experience_import_service import (
    import_community_experience_seed,
)


def test_community_seed_import_is_idempotent_and_unverified(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    seed_path = source_dir / "community_experience_seed.md"
    seed_path.write_text("# 社区经验\n\n厚显卡需要核对底部风扇空间。", encoding="utf-8")
    manifest_path = source_dir / "community_experience_manifest.json"
    manifest_path.write_text(
        json.dumps({"entries": [{"id": "CE-001"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    upload_dir = tmp_path / "backend" / "uploads" / "knowledge"
    backend_dir = tmp_path / "backend"

    with Session(engine) as db:
        first = import_community_experience_seed(
            db,
            seed_path=seed_path,
            manifest_path=manifest_path,
            upload_dir=upload_dir,
            backend_dir=backend_dir,
        )
        second = import_community_experience_seed(
            db,
            seed_path=seed_path,
            manifest_path=manifest_path,
            upload_dir=upload_dir,
            backend_dir=backend_dir,
        )

        document = db.scalar(select(KnowledgeDocument))
        assert first["imported"] == 1
        assert second["skipped"] == 1
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1
        assert document.source_type == "community_experience"
        assert document.document_type == "community_experience_seed"
        assert document.product_category == "community_experience"
        assert document.verified is False
        assert document.needs_review is False
        assert seed_path.read_text(encoding="utf-8").startswith("# 社区经验")
        assert (backend_dir / document.file_path).is_file()
