"""Application configuration loaded from environment (pydantic-settings).

All environment access goes through Settings. No code reads os.environ directly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repo-root .env (backend runs from backend/ in dev; tests run from repo root).
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Pramya backend settings.

    Values come from environment variables (or .env in local dev).
    Field names map to env vars case-insensitively: `app_env` -> APP_ENV.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: str = "development"
    app_name: str = "pramya"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8001, gt=0, lt=65536)
    api_prefix: str = "/api/v1"

    # Database (PostgreSQL + pgvector)
    database_url: str = "postgresql+asyncpg://pramya:pramya@localhost:5432/pramya"
    db_echo: bool = False

    # DeepSeek (production text LLM; ADR-023 — all textual inference)
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: float = 60.0

    # Provider topology (ADR-023): TEXT -> DeepSeek, AUDIO -> local oMLX.
    llm_provider: str = "deepseek"
    voice_provider: str = "omlx"

    # Local AI runtime (oMLX)
    local_ai_enabled: bool = True
    local_ai_runtime: str = "omlx"
    # Verified against the local runtime (2026-08): oMLX listens on
    # 127.0.0.1:8000 and serves OpenAI-compatible endpoints under /v1
    # (docs/operations/DEPLOYMENT.md).
    omlx_base_url: str = "http://127.0.0.1:8000/v1"
    omlx_api_key: str | None = None
    # Canonical model IDs registered in the running oMLX (/v1/models):
    # audio (Qwen3-ASR / parakeet / Qwen3-TTS) + retrieval (bge-m3,
    # Qwen3-Reranker). Local text generation is PROHIBITED in production
    # (ADR-023); OMLX_CHAT_MODEL is construction-compat only.
    omlx_chat_model: str = "pramya-4b"  # UNUSED by routing (ADR-023); construction compat only
    omlx_embedding_model: str = "bge-m3-mlx-4bit"
    omlx_rerank_model: str = "Qwen3-Reranker-0.6B-4bit"
    # Thinking-off for any local text model. Never relied on: text routing
    # targets DeepSeek (ADR-023); local text generation is prohibited.
    omlx_pramya_thinking_enabled: bool = False
    omlx_timeout_seconds: float = 120.0

    # Voice (oMLX speech models; explicit live/offline split — ADR-023, H.4)
    voice_live_asr_model: str = "parakeet-tdt-0.6b-v3-int8"  # live ASR (primary)
    voice_offline_asr_model: str = "Qwen3-ASR-1.7B-4bit"  # offline/archival ASR
    voice_tts_model: str = "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit"
    # Legacy aliases (construction compat; prefer voice_* fields).
    omlx_asr_model: str = "Qwen3-ASR-1.7B-4bit"  # deprecated: use voice_offline_asr_model
    omlx_asr_optional_model: str = (  # deprecated: use voice_live_asr_model
        "parakeet-tdt-0.6b-v3-int8"
    )
    omlx_tts_model: str = "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit"  # deprecated: use voice_tts_model
    voice_retention_days: int = 30
    # Opt-in: persist candidate audio as WAV under audio_storage_dir and write
    # audio_segment rows (replay/retention). Off disables audio persistence.
    voice_store_audio: bool = True
    audio_storage_dir: str = ".runtime/audio"
    # Turn finalization: silence (s) after speech ends auto-ends the turn.
    voice_silence_seconds: float = 1.5
    # RMS energy threshold (0-32767) to consider speech present.
    voice_speech_rms: float = 400.0
    # Streaming playback chunk (samples per PCM16 audio_chunk frame).
    voice_chunk_samples: int = 4800  # 200 ms @ 24 kHz

    @property
    def audio_storage_path(self) -> Path:
        """Absolute audio storage dir (relative paths anchor to repo root)."""
        p = Path(self.audio_storage_dir).expanduser()
        if not p.is_absolute():
            p = _ENV_FILE.parent / p
        return p

    # Uploads
    upload_max_mb: int = 5
    upload_storage_dir: str = ".runtime/uploads"
    # Document parsing guards (Phase 2.1): configurable conservative defaults.
    # Page limit bounds PDF parsing resource use; timeout bounds total parse
    # time at the service boundary (asyncio.wait_for over asyncio.to_thread).
    document_max_pages: int = 50
    document_parse_timeout_seconds: float = 30.0

    # Knowledge ingestion (Phase 2.2): chunking + embedding batch size.
    knowledge_chunk_size: int = 1200
    knowledge_chunk_overlap: int = 200
    knowledge_embed_batch_size: int = 8

    # Observability (Langfuse optional)
    # Langfuse OSS (self-hosted, MIT-licensed) is the V1 observability platform.
    # Langfuse Cloud and Enterprise-only features are NOT V1 dependencies.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    # CORS (comma-separated string in env: CORS_ORIGINS=a,b)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Accept comma-separated env string (CORS_ORIGINS=a,b) or a JSON list."""
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return parts or ["http://localhost:3000"]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
