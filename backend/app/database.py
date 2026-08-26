"""SQLAlchemy database setup and initialization helpers."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield one database session for FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    """Create all tables registered on Base metadata.

    Call this after MySQL is available when models are added to the project.
    """
    # Import models here so their tables are registered even if routers change.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # create_all does not add columns to an existing table. Apply this small,
    # backward-compatible upgrade without deleting existing chunk data.
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("knowledge_chunks")}
    with engine.begin() as connection:
        if "page_number" not in columns:
            connection.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN page_number INTEGER NULL"))
        if "section_title" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE knowledge_chunks "
                    "ADD COLUMN section_title VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
        if engine.dialect.name == "mysql":
            chunk_content_charset = connection.execute(
                text(
                    "SELECT CHARACTER_SET_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = :schema_name "
                    "AND TABLE_NAME = 'knowledge_chunks' AND COLUMN_NAME = 'content'"
                ),
                {"schema_name": settings.mysql_database},
            ).scalar_one_or_none()
            if chunk_content_charset != "utf8mb4":
                connection.execute(
                    text(
                        "ALTER TABLE knowledge_chunks "
                        "MODIFY content TEXT CHARACTER SET utf8mb4 "
                        "COLLATE utf8mb4_unicode_ci NOT NULL, "
                        "MODIFY section_title VARCHAR(255) CHARACTER SET utf8mb4 "
                        "COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT ''"
                    )
                )
        document_columns = {
            column["name"] for column in inspector.get_columns("knowledge_documents")
        }
        if "file_hash" not in document_columns:
            connection.execute(
                text("ALTER TABLE knowledge_documents ADD COLUMN file_hash VARCHAR(64) NULL")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX uq_knowledge_documents_file_hash "
                    "ON knowledge_documents (file_hash)"
                )
            )
        if "status" not in document_columns:
            connection.execute(
                text(
                    "ALTER TABLE knowledge_documents ADD COLUMN status "
                    "VARCHAR(20) NOT NULL DEFAULT 'pending'"
                )
            )
        document_columns = {
            column["name"] for column in inspector.get_columns("knowledge_documents")
        }
        knowledge_additions = {
            "original_filename": "VARCHAR(255) NOT NULL DEFAULT ''",
            "vendor": "VARCHAR(128) NOT NULL DEFAULT ''",
            "product_name": "VARCHAR(255) NOT NULL DEFAULT ''",
            "product_category": "VARCHAR(64) NOT NULL DEFAULT ''",
            "document_type": "VARCHAR(64) NOT NULL DEFAULT ''",
            "source_url": "VARCHAR(2048) NOT NULL DEFAULT ''",
            "file_url": "VARCHAR(2048) NOT NULL DEFAULT ''",
            "support_url": "VARCHAR(2048) NOT NULL DEFAULT ''",
            "verified": "BOOLEAN NOT NULL DEFAULT 0",
            "needs_review": "BOOLEAN NOT NULL DEFAULT 0",
            "source_type": "VARCHAR(64) NOT NULL DEFAULT ''",
            "version": "VARCHAR(32) NOT NULL DEFAULT '1.0'",
            "chunk_count": "INTEGER NOT NULL DEFAULT 0",
            "embedding_status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "updated_time": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        }
        for column_name, definition in knowledge_additions.items():
            if column_name not in document_columns:
                connection.execute(
                    text(f"ALTER TABLE knowledge_documents ADD COLUMN {column_name} {definition}")
                )
        connection.execute(
            text(
                "UPDATE knowledge_documents SET embedding_status = status "
                "WHERE status IN ('pending', 'processing', 'completed', 'failed')"
            )
        )
        connection.execute(
            text(
                "UPDATE knowledge_documents SET embedding_status = 'completed' "
                "WHERE embedding_status = 'success' OR status = 'success'"
            )
        )
        connection.execute(
            text(
                "UPDATE knowledge_documents SET status = 'active' "
                "WHERE status NOT IN ('active', 'inactive')"
            )
        )
        connection.execute(
            text(
                "UPDATE knowledge_documents d SET chunk_count = "
                "(SELECT COUNT(*) FROM knowledge_chunks c WHERE c.document_id = d.id)"
            )
        )
        connection.execute(
            text(
                "UPDATE knowledge_documents SET original_filename = filename "
                "WHERE original_filename = ''"
            )
        )
        message_columns = {column["name"] for column in inspector.get_columns("messages")}
        if "metadata_json" not in message_columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN metadata_json JSON NULL"))
        session_columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
        if "updated_time" not in session_columns:
            connection.execute(
                text(
                    "ALTER TABLE chat_sessions ADD COLUMN updated_time DATETIME "
                    "NOT NULL DEFAULT CURRENT_TIMESTAMP"
                )
            )
        evaluation_case_columns = {
            column["name"] for column in inspector.get_columns("evaluation_cases")
        }
        if "category" not in evaluation_case_columns:
            connection.execute(
                text(
                    "ALTER TABLE evaluation_cases ADD COLUMN category "
                    "VARCHAR(32) NOT NULL DEFAULT 'general'"
                )
            )
            connection.execute(
                text("CREATE INDEX ix_evaluation_cases_category ON evaluation_cases (category)")
            )
        evaluation_result_columns = {
            column["name"] for column in inspector.get_columns("evaluation_results")
        }
        if "expected_tool" not in evaluation_result_columns:
            connection.execute(
                text(
                    "ALTER TABLE evaluation_results ADD COLUMN expected_tool "
                    "VARCHAR(128) NOT NULL DEFAULT ''"
                )
            )
        if "actual_tool" not in evaluation_result_columns:
            connection.execute(
                text(
                    "ALTER TABLE evaluation_results ADD COLUMN actual_tool "
                    "VARCHAR(128) NOT NULL DEFAULT ''"
                )
            )
    from app.services.evaluation_service import seed_default_cases
    from app.services.agent_config_service import seed_agent_configs

    with SessionLocal() as db:
        seed_default_cases(db)
        seed_agent_configs(db)
