"""Persistent Chroma storage and similarity search service."""

from pathlib import Path
from threading import Lock
from typing import NotRequired, TypedDict

import chromadb
from chromadb.api.models.Collection import Collection

from app.services.embedding_service import EmbeddingService, embedding_service


BACKEND_DIR = Path(__file__).resolve().parents[2]
CHROMA_PATH = BACKEND_DIR / "vector_store" / "chroma"
COLLECTION_NAME = "knowledge_chunks"


class ChunkInput(TypedDict):
    id: int
    content: str
    document_id: NotRequired[int]
    filename: NotRequired[str]
    original_filename: NotRequired[str]
    product_name: NotRequired[str]
    source_type: NotRequired[str]
    embedding_status: NotRequired[str]
    page_number: NotRequired[int | None]
    section_title: NotRequired[str]


class VectorSearchResult(TypedDict):
    chunk_id: int
    document_id: int
    content: str
    distance: float
    filename: str
    original_filename: str
    product_name: str
    source_type: str
    embedding_status: str
    page_number: int | None
    section_title: str


class VectorService:
    """Store chunk vectors in a local persistent Chroma collection."""

    def __init__(
        self,
        persist_path: Path = CHROMA_PATH,
        embedding: EmbeddingService = embedding_service,
    ) -> None:
        self.persist_path = persist_path
        self.embedding = embedding
        self._collection: Collection | None = None
        self._collection_lock = Lock()

    def _get_collection(self) -> Collection:
        """Create the persistent cosine-distance collection on first use."""
        if self._collection is None:
            with self._collection_lock:
                if self._collection is None:
                    self.persist_path.mkdir(parents=True, exist_ok=True)
                    client = chromadb.PersistentClient(path=str(self.persist_path))
                    self._collection = client.get_or_create_collection(
                        name=COLLECTION_NAME,
                        embedding_function=None,
                        configuration={"hnsw": {"space": "cosine"}},
                    )
        return self._collection

    def add_documents(
        self,
        chunks: list[ChunkInput],
        document_id: int | None = None,
    ) -> int:
        """Embed and upsert chunks, optionally replacing one document's vectors."""
        if not chunks:
            return 0

        contents = [chunk["content"] for chunk in chunks]
        vectors = self.embedding.encode(contents)
        collection = self._get_collection()
        if document_id is not None:
            collection.delete(where={"document_id": document_id})
        ids = [str(chunk["id"]) for chunk in chunks]
        metadatas = [
            {
                "chunk_id": chunk["id"],
                "document_id": document_id
                if document_id is not None
                else chunk.get("document_id", 0),
                "filename": chunk.get("filename", ""),
                "original_filename": chunk.get("original_filename", ""),
                "product_name": chunk.get("product_name", ""),
                "source_type": chunk.get("source_type", ""),
                "embedding_status": chunk.get("embedding_status", "completed"),
                "page_number": chunk.get("page_number") or 0,
                "section_title": chunk.get("section_title", ""),
            }
            for chunk in chunks
        ]
        collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=contents,
            metadatas=metadatas,
        )
        return len(chunks)

    def update_document_metadata(
        self,
        document_id: int,
        metadata: dict[str, str],
    ) -> int:
        """Merge document metadata into existing vectors without re-embedding."""
        collection = self._get_collection()
        response = collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        ids = response.get("ids", [])
        existing_metadatas = response.get("metadatas", []) or []
        if not ids:
            return 0
        merged = [
            {
                **(current or {}),
                **{key: value for key, value in metadata.items() if value is not None},
                "document_id": document_id,
            }
            for current in existing_metadatas
        ]
        collection.update(ids=ids, metadatas=merged)
        return len(ids)

    def inspect_document(self, document_id: int, sample_limit: int = 3) -> dict:
        """Return vector count and bounded metadata samples for diagnostics."""
        collection = self._get_collection()
        response = collection.get(
            where={"document_id": document_id},
            limit=sample_limit,
            include=["metadatas", "documents"],
        )
        return {
            "document_id": document_id,
            "vector_count": self.count_documents(document_id),
            "ids": response.get("ids", []),
            "metadatas": response.get("metadatas", []) or [],
            "documents": response.get("documents", []) or [],
        }

    def count_documents(self, document_id: int) -> int:
        """Return the number of vectors currently stored for one document."""
        response = self._get_collection().get(
            where={"document_id": document_id},
            include=[],
        )
        return len(response.get("ids", []))

    def search(
        self, query: str, top_k: int, document_ids: list[int] | None = None
    ) -> list[VectorSearchResult]:
        """Return the nearest stored chunks for a query embedding."""
        collection = self._get_collection()
        stored_count = collection.count()
        if stored_count == 0:
            return []

        query_vector = self.embedding.encode([query])[0]
        if document_ids == []:
            return []
        response = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, stored_count),
            where={"document_id": {"$in": document_ids}} if document_ids is not None else None,
            include=["documents", "metadatas", "distances"],
        )
        documents = response["documents"][0] if response["documents"] else []
        metadatas = response["metadatas"][0] if response["metadatas"] else []
        distances = response["distances"][0] if response["distances"] else []

        results: list[VectorSearchResult] = []
        for content, metadata, distance in zip(documents, metadatas, distances):
            metadata = metadata or {}
            results.append(
                {
                    "chunk_id": int(metadata.get("chunk_id", 0)),
                    "document_id": int(metadata.get("document_id", 0)),
                    "content": content or "",
                    "distance": float(distance),
                    "filename": str(metadata.get("filename", "")),
                    "original_filename": str(metadata.get("original_filename", "")),
                    "product_name": str(metadata.get("product_name", "")),
                    "source_type": str(metadata.get("source_type", "")),
                    "embedding_status": str(metadata.get("embedding_status", "")),
                    "page_number": (
                        int(metadata["page_number"])
                        if metadata.get("page_number")
                        else None
                    ),
                    "section_title": str(metadata.get("section_title", "")),
                }
            )
        return results


vector_service = VectorService()
