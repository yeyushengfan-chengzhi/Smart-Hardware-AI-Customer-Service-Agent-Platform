"""Backfill Chroma document metadata without deleting or re-embedding vectors."""

import json
import sys
from pathlib import Path

from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_database  # noqa: E402
from app.models.knowledge_document import KnowledgeDocument  # noqa: E402
from app.services.knowledge_service import (  # noqa: E402
    RETRIEVABLE_EMBEDDING_STATUSES,
)
from app.services.vector_service import vector_service  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    init_database()
    with SessionLocal() as db:
        documents = list(db.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.status == "active",
                KnowledgeDocument.embedding_status.in_(
                    RETRIEVABLE_EMBEDDING_STATUSES
                ),
            )
        ).all())
        updated_vectors = 0
        details = []
        for document in documents:
            count = vector_service.update_document_metadata(
                document.id,
                {
                    "filename": document.filename,
                    "original_filename": document.original_filename,
                    "product_name": document.product_name,
                    "source_type": document.source_type,
                    "embedding_status": "completed",
                },
            )
            if document.embedding_status == "success":
                document.embedding_status = "completed"
            updated_vectors += count
            details.append({"document_id": document.id, "vectors": count})
        db.commit()
    print(json.dumps(
        {
            "documents": len(documents),
            "updated_vectors": updated_vectors,
            "details": details,
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
