"""Knowledge base document database model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KnowledgeDocument(Base):
    """Metadata for a file stored in the enterprise knowledge base."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    vendor: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    product_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    product_category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    support_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active", index=True
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", index=True
    )
    created_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
