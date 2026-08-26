"""Inspect one document in DB/Chroma and run read-only RAG queries."""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models.knowledge_chunk import KnowledgeChunk  # noqa: E402
from app.models.knowledge_document import KnowledgeDocument  # noqa: E402
from app.services.rag_service import rag_service  # noqa: E402
from app.services.vector_service import vector_service  # noqa: E402


def _document_status(document_id: int) -> dict:
    with SessionLocal() as db:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            return {"document_id": document_id, "found": False}
        chunk_count = db.scalar(
            select(func.count(KnowledgeChunk.id)).where(
                KnowledgeChunk.document_id == document_id
            )
        )
        vector_status = vector_service.inspect_document(document_id)
        return {
            "document_id": document_id,
            "found": True,
            "filename": document.filename,
            "original_filename": document.original_filename,
            "product_name": document.product_name,
            "source_type": document.source_type,
            "status": document.status,
            "embedding_status": document.embedding_status,
            "db_chunk_count": int(chunk_count or 0),
            "vector_count": vector_status["vector_count"],
            "metadata_samples": vector_status["metadatas"],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", type=int)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    output: dict[str, object] = {}
    if args.document_id is not None:
        output["document"] = _document_status(args.document_id)
    output["queries"] = [
        {
            "query": query,
            "results": rag_service.search(query, args.top_k),
        }
        for query in args.query
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
