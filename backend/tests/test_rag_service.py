import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.knowledge_document import KnowledgeDocument
from app.services.rag_service import (
    RAGService,
    _active_document_ids_from_db,
    _matching_active_document_ids_from_db,
    keyword_score,
)


class FakeVectorService:
    def __init__(self):
        self.requested_query = ""
        self.requested_top_k = 0

    def search(self, query: str, top_k: int):
        self.requested_query = query
        self.requested_top_k = top_k
        base = {
            "document_id": 2,
            "filename": "manual.pdf",
            "section_title": "",
        }
        return [
            {
                **base,
                "chunk_id": 51,
                "page_number": 51,
                "section_title": "简易侦错 LED 灯",
                "content": "白色 GPU 无法检测或故障，黄色 DRAM 无法检测或故障。",
                "distance": 0.25,
            },
            {
                **base,
                "chunk_id": 9,
                "page_number": 9,
                "content": "主板存放温度警告。",
                "distance": 0.20,
            },
            {
                **base,
                "chunk_id": 51,
                "page_number": 51,
                "content": "duplicate",
                "distance": 0.30,
            },
            {
                **base,
                "chunk_id": 52,
                "page_number": 52,
                "content": "白色 GPU 无法检测或故障，黄色 DRAM 无法检测或故障。",
                "distance": 0.26,
            },
        ]


def test_keyword_score_supports_chinese_english_and_title_weight():
    score = keyword_score(
        "主板白色故障灯一直亮",
        "白色 GPU 无法检测或故障",
        "简易侦错 LED 灯",
    )
    assert 0.0 < score <= 1.0


def test_top20_hybrid_threshold_metadata_and_deduplication():
    vectors = FakeVectorService()
    service = RAGService(vectors=vectors, similarity_threshold=0.60, candidate_count=20)

    results = service.search("我的主板开机没有显示怎么办", 3)

    assert vectors.requested_top_k == 20
    assert "简易侦错" in vectors.requested_query
    assert results[0]["chunk_id"] == 51
    assert results[0]["filename"] == "manual.pdf"
    assert results[0]["page_number"] == 51
    assert results[0]["semantic_score"] == 0.75
    assert results[0]["score"] >= 0.60
    assert len({item["chunk_id"] for item in results}) == len(results)
    assert all(item["content"] != "主板存放温度警告。" for item in results)


def test_active_document_filter_is_forwarded_to_vector_search():
    class FilterAwareVectors(FakeVectorService):
        def __init__(self):
            super().__init__()
            self.document_ids = None

        def search(self, query, top_k, document_ids=None):
            self.document_ids = document_ids
            return []

    vectors = FilterAwareVectors()
    service = RAGService(
        vectors=vectors, similarity_threshold=0.6, candidate_count=20,
        active_document_ids_provider=lambda: [3, 7],
    )
    service.search("B850主板支持DDR5吗", 3)
    assert vectors.document_ids == [3, 7]


def test_complete_product_name_scope_takes_precedence():
    class FilterAwareVectors(FakeVectorService):
        def __init__(self):
            super().__init__()
            self.document_ids = None

        def search(self, query, top_k, document_ids=None):
            self.document_ids = document_ids
            return []

    vectors = FilterAwareVectors()
    service = RAGService(
        vectors=vectors,
        similarity_threshold=0.6,
        candidate_count=20,
        active_document_ids_provider=lambda: [3, 7],
        query_document_ids_provider=lambda query: (
            [13] if "B850M-PLUS" in query else []
        ),
    )
    service.search("TUF GAMING B850M-PLUS WIFI 的 Debug LED 是什么意思？", 3)
    assert vectors.document_ids == [13]


def test_product_scoped_result_is_not_dropped_by_global_threshold():
    class ProductVectors:
        def search(self, query, top_k, document_ids=None):
            assert document_ids == [35]
            return [{
                "chunk_id": 23755,
                "document_id": 35,
                "filename": "LIAN_LI_LANCOOL_216_case_manual.pdf",
                "original_filename": "LANCOOL216_Manual.pdf",
                "product_name": "LANCOOL 216",
                "source_type": "official_manual_seed",
                "embedding_status": "completed",
                "page_number": 1,
                "section_title": "Case Components",
                "content": "Supporting 360 mm radiator x 1 or 280 mm radiator x 1",
                "distance": 0.3923,
            }]

    service = RAGService(
        vectors=ProductVectors(),
        similarity_threshold=0.60,
        candidate_count=20,
        query_document_ids_provider=lambda query: [35],
    )
    results = service.search("LANCOOL 216 radiator", 3)

    assert results
    assert results[0]["document_id"] == 35
    assert results[0]["filename"] == "LIAN_LI_LANCOOL_216_case_manual.pdf"
    assert results[0]["score"] >= 0.60


def test_success_and_completed_documents_are_retrievable_by_metadata():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[KnowledgeDocument.__table__])
    with Session(engine) as db:
        db.add_all([
            KnowledgeDocument(
                id=35, filename="LIAN_LI_LANCOOL_216_case_manual.pdf",
                original_filename="LANCOOL216_Manual.pdf", vendor="LIAN LI",
                product_name="LANCOOL 216", file_path="one.pdf", file_type="pdf",
                status="active", embedding_status="completed",
            ),
            KnowledgeDocument(
                id=50, filename="JONSBO_Z20_case_manual.pdf",
                original_filename="Z20_Installation_Manual.pdf", vendor="JONSBO",
                product_name="Z20", file_path="two.pdf", file_type="pdf",
                status="active", embedding_status="success",
            ),
            KnowledgeDocument(
                id=60, filename="inactive.pdf", original_filename="inactive.pdf",
                vendor="MSI", product_name="MAG B760M MORTAR WIFI DDR4",
                file_path="three.pdf", file_type="pdf",
                status="inactive", embedding_status="completed",
            ),
        ])
        db.commit()

        assert set(_active_document_ids_from_db(db)) == {35, 50}
        assert _matching_active_document_ids_from_db(
            db, "LIAN LI LANCOOL 216 支持多大水冷？"
        ) == [35]
        assert _matching_active_document_ids_from_db(
            db, "JONSBO Z20 支持什么尺寸主板？"
        ) == [50]


@pytest.mark.parametrize(
    ("query", "document_id", "filename"),
    [
        (
            "LANCOOL 216 radiator",
            35,
            "LIAN_LI_LANCOOL_216_case_manual.pdf",
        ),
        (
            "LIAN LI LANCOOL 216 支持多大水冷？",
            35,
            "LIAN_LI_LANCOOL_216_case_manual.pdf",
        ),
        (
            "JONSBO Z20 支持什么尺寸主板？",
            50,
            "JONSBO_Z20_case_manual.pdf",
        ),
        (
            "MSI MAG B760M MORTAR WIFI DDR4 支持 DDR4 吗？",
            33,
            "MSI_MAG_B760M_MORTAR_WIFI_DDR4_motherboard_manual.pdf",
        ),
    ],
)
def test_manual_seed_product_queries_return_expected_document(
    query, document_id, filename
):
    contents = {
        35: "Supporting 360 mm radiator and 280 mm radiator water cooling.",
        50: "Motherboard form factor installation for the JONSBO Z20 case.",
        33: "MAG B760M MORTAR WIFI DDR4 supports DDR4 DIMM memory.",
    }

    class ProductVectors:
        def search(self, expanded_query, top_k, document_ids=None):
            assert document_ids == [document_id]
            return [{
                "chunk_id": document_id * 100,
                "document_id": document_id,
                "filename": filename,
                "original_filename": filename,
                "product_name": filename,
                "source_type": "official_manual_seed",
                "embedding_status": "completed",
                "page_number": 1,
                "section_title": "Specifications",
                "content": contents[document_id],
                "distance": 0.45,
            }]

    service = RAGService(
        vectors=ProductVectors(),
        similarity_threshold=0.60,
        query_document_ids_provider=lambda value: [document_id],
    )

    results = service.search(query, 3)

    assert results
    assert results[0]["document_id"] == document_id
    assert results[0]["filename"] == filename
