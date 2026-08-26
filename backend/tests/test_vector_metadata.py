from pathlib import Path

from app.services.vector_service import VectorService


class FakeEmbedding:
    def encode(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FakeCollection:
    def __init__(self):
        self.upsert_args = None
        self.update_args = None

    def delete(self, **kwargs):
        pass

    def upsert(self, **kwargs):
        self.upsert_args = kwargs

    def get(self, **kwargs):
        if kwargs.get("include") == []:
            return {"ids": ["1"]}
        return {
            "ids": ["1"],
            "metadatas": [{"chunk_id": 1, "document_id": 2}],
            "documents": ["x"],
        }

    def update(self, **kwargs):
        self.update_args = kwargs


def test_vector_metadata_contains_document_source_fields():
    service = VectorService(Path("unused"), FakeEmbedding())
    collection = FakeCollection()
    service._collection = collection
    service.add_documents(
        [{
            "id": 1,
            "document_id": 2,
            "content": "x",
            "filename": "m.pdf",
            "original_filename": "original.pdf",
            "product_name": "LANCOOL 216",
            "source_type": "official_manual_seed",
            "embedding_status": "completed",
            "page_number": 51,
            "section_title": "LED",
        }],
        document_id=2,
    )
    assert collection.upsert_args["metadatas"][0] == {
        "chunk_id": 1,
        "document_id": 2,
        "filename": "m.pdf",
        "original_filename": "original.pdf",
        "product_name": "LANCOOL 216",
        "source_type": "official_manual_seed",
        "embedding_status": "completed",
        "page_number": 51,
        "section_title": "LED",
    }


def test_vector_metadata_can_be_backfilled_without_reembedding():
    service = VectorService(Path("unused"), FakeEmbedding())
    collection = FakeCollection()
    service._collection = collection

    updated = service.update_document_metadata(
        2,
        {
            "filename": "m.pdf",
            "product_name": "LANCOOL 216",
            "source_type": "official_manual_seed",
            "embedding_status": "completed",
        },
    )

    assert updated == 1
    assert collection.update_args["ids"] == ["1"]
    assert collection.update_args["metadatas"][0]["chunk_id"] == 1
    assert collection.update_args["metadatas"][0]["product_name"] == "LANCOOL 216"
