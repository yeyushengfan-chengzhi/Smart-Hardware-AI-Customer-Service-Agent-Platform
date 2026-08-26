from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.document_parser_service import ChunkData
from app.services import knowledge_pipeline_service as pipeline


class FakeVectors:
    def __init__(self):
        self.calls = []

    def add_documents(self, chunks, document_id=None):
        self.calls.append((document_id, chunks))
        return len(chunks)

    def count_documents(self, document_id):
        return sum(
            len(chunks) for stored_id, chunks in self.calls if stored_id == document_id
        )


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[KnowledgeDocument.__table__, KnowledgeChunk.__table__]
    )
    return sessionmaker(bind=engine), engine


def _fake_parse(db, document_id):
    if not db.scalar(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.document_id == document_id
        )
    ):
        db.add(
            KnowledgeChunk(
                document_id=document_id,
                content="hardware manual content",
                chunk_index=0,
                section_title="manual",
            )
        )
        db.commit()
    return 1


def test_new_file_is_created_processed_and_second_run_is_incremental(tmp_path, monkeypatch):
    factory, engine = _factory()
    upload_dir = tmp_path / "uploads" / "knowledge"
    upload_dir.mkdir(parents=True)
    (upload_dir / "ASUS.txt").write_text("new manual", encoding="utf-8")
    monkeypatch.setattr(pipeline, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline,
        "build_document_chunks",
        lambda document: [ChunkData("hardware manual content", 1, "manual")],
        raising=False,
    )
    vectors = FakeVectors()

    first = pipeline.process_directory(factory, upload_dir, vectors)
    second = pipeline.process_directory(factory, upload_dir, vectors)

    assert first[0].status == "completed"
    assert first[0].chunk_count == first[0].embedding_count == 1
    assert second[0].status == "completed"
    assert second[0].embedding_count == 1
    assert len(vectors.calls) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1
        assert db.scalar(select(func.count(KnowledgeChunk.id))) == 1


def test_same_content_with_different_filename_is_duplicate(tmp_path, monkeypatch):
    factory, engine = _factory()
    upload_dir = tmp_path / "uploads" / "knowledge"
    upload_dir.mkdir(parents=True)
    (upload_dir / "ASUS.txt").write_text("identical", encoding="utf-8")
    (upload_dir / "MSI_copy.txt").write_text("identical", encoding="utf-8")
    monkeypatch.setattr(pipeline, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline,
        "build_document_chunks",
        lambda document: [ChunkData("hardware manual content", 1, "manual")],
        raising=False,
    )

    results = pipeline.process_directory(factory, upload_dir, FakeVectors())

    assert [result.status for result in results] == ["completed", "duplicate"]
    with Session(engine) as db:
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1


def test_replaced_file_content_is_reprocessed_by_hash(tmp_path, monkeypatch):
    factory, engine = _factory()
    upload_dir = tmp_path / "uploads" / "knowledge"
    upload_dir.mkdir(parents=True)
    path = upload_dir / "manual.txt"
    path.write_text("version one", encoding="utf-8")
    monkeypatch.setattr(pipeline, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline,
        "build_document_chunks",
        lambda document: [ChunkData("hardware manual content", 1, "manual")],
    )
    vectors = FakeVectors()

    first = pipeline.process_directory(factory, upload_dir, vectors)
    first_hash = first[0].file_hash
    path.write_text("version two", encoding="utf-8")
    second = pipeline.process_directory(factory, upload_dir, vectors)

    assert first[0].status == "completed"
    assert second[0].status == "completed"
    assert second[0].file_hash != first_hash
    assert len(vectors.calls) == 2
    with Session(engine) as db:
        document = db.scalar(select(KnowledgeDocument))
        assert document.file_hash == second[0].file_hash
        assert document.status == "active"
        assert document.embedding_status == "completed"
        assert db.scalar(select(func.count(KnowledgeDocument.id))) == 1


def test_failure_does_not_stop_other_files(tmp_path, monkeypatch):
    factory, engine = _factory()
    upload_dir = tmp_path / "uploads" / "knowledge"
    upload_dir.mkdir(parents=True)
    (upload_dir / "bad.txt").write_text("broken", encoding="utf-8")
    (upload_dir / "good.txt").write_text("valid", encoding="utf-8")
    monkeypatch.setattr(pipeline, "BACKEND_DIR", tmp_path)

    def parse_with_failure(document):
        if document.filename == "bad.txt":
            raise ValueError("unable to parse document")
        return [ChunkData("hardware manual content", 1, "manual")]

    monkeypatch.setattr(pipeline, "build_document_chunks", parse_with_failure)
    results = pipeline.process_directory(factory, upload_dir, FakeVectors())

    assert [result.status for result in results] == ["failed", "completed"]
    assert "unable to parse" in results[0].error
    with Session(engine) as db:
        statuses = dict(
            db.execute(
                select(KnowledgeDocument.filename, KnowledgeDocument.embedding_status)
            ).all()
        )
        assert statuses == {"bad.txt": "failed", "good.txt": "completed"}
