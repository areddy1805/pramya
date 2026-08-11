"""Application configuration loaded from environment (pydantic-settings).

All environment access goes through Settings. No code reads os.environ directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pramya backend settings.

    Values come from environment variables (or .env in local dev).
    Field names map to env vars case-insensitively: `app_env` -> APP_ENV.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: str = "development"
    app_name: str = "pramya"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, gt=0, lt=65536)
    api_prefix: str = "/api/v1"

    # Database (PostgreSQL + pgvector)
    database_url: str = "postgresql+asyncpg://pramya:pramya@localhost:5432/pramya"
    db_echo: bool = False

    # DeepSeek (cloud reasoning)
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"

    # Local AI runtime (oMLX)
    local_ai_enabled: bool = True
    local_ai_runtime: str = "omlx"
    omlx_base_url: str = "http://127.0.0.1:7799"
    omlx_api_key: str | None = None

    # Voice
    voice_retention_days: int = 30
    audio_storage_dir: str = ".runtime/audio"

    # Uploads
    upload_max_mb: int = 5
    upload_storage_dir: str = ".runtime/uploads"

    # Observability (Langfuse optional)
    # Langfuse OSS (self-hosted, MIT-licensed) is the V1 observability platform.
    # Langfuse Cloud and Enterprise-only features are NOT V1 dependencies.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
