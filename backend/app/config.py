"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development").strip().lower()
        self.mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
        self.mysql_user = os.getenv("MYSQL_USER", "root")
        self.mysql_password = os.getenv("MYSQL_PASSWORD", "")
        self.mysql_database = os.getenv("MYSQL_DATABASE", "smart_agent")
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "change-this-secret-in-production")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
        self.similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.60"))
        self.rag_candidate_count = int(os.getenv("RAG_CANDIDATE_COUNT", "20"))
        self.llm_provider = os.getenv("LLM_PROVIDER", "deepseek")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_model = os.getenv("LLM_MODEL", "deepseek-chat")

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy MySQL connection URL."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@"
            f"{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
