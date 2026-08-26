from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.document_parser_service import ChunkData
from app.services import reindex_service


class FakeVectors:
    def __init__(self, fail=False):
        self.fail = fail
        self.payload = []

    def add_documents(self, chunks, document_id=None):
        if self.fail:
            raise RuntimeError("vector failure")
        self.payload = chunks
        return len(chunks)


def _database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[KnowledgeDocument.__table__, KnowledgeChunk.__table__],
    )
    return engine


def test_reindex_replaces_only_requested_document(monkeypatch):
    engine = _database()
    with Session(engine) as db:
        document = KnowledgeDocument(filename="m.pdf", file_path="uploads/knowledge/m.pdf", file_type="pdf")
        other = KnowledgeDocument(filename="other.pdf", file_path="uploads/knowledge/o.pdf", file_type="pdf")
        db.add_all([document, other])
        db.flush()
        db.add_all([
            KnowledgeChunk(document_id=document.id, content="old", chunk_index=0, section_title=""),
            KnowledgeChunk(document_id=other.id, content="untouched", chunk_index=0, section_title=""),
        ])
        db.commit()
        monkeypatch.setattr(
            reindex_service,
            "build_document_chunks",
            lambda _: [ChunkData("new LED content", 51, "简易侦错 LED 灯")],
        )
        stats = reindex_service.reindex_document(db, document.id, FakeVectors())
        assert stats["old_chunks"] == stats["new_chunks"] == stats["vectors"] == 1
        assert db.scalar(select(KnowledgeChunk.content).where(KnowledgeChunk.document_id == other.id)) == "untouched"


def test_reindex_rolls_back_database_when_vectorization_fails(monkeypatch):
    engine = _database()
    with Session(engine) as db:
        document = KnowledgeDocument(filename="m.pdf", file_path="uploads/knowledge/m.pdf", file_type="pdf")
        db.add(document)
        db.flush()
        db.add(KnowledgeChunk(document_id=document.id, content="old", chunk_index=0, section_title=""))
        db.commit()
        monkeypatch.setattr(
            reindex_service,
            "build_document_chunks",
            lambda _: [ChunkData("new", 1, "title")],
        )
        try:
            reindex_service.reindex_document(db, document.id, FakeVectors(fail=True))
        except RuntimeError:
            pass
        assert db.scalar(select(KnowledgeChunk.content).where(KnowledgeChunk.document_id == document.id)) == "old"
