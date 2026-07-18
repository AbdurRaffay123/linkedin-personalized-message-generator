"""Application configuration, loaded from environment / .env.

All secrets and tunables live here. Nothing else in the codebase should read
os.environ directly — import `settings` instead.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "AI Sales Assistant"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # --- Database ---
    # SQLite for MVP; swap to a postgresql+psycopg URL for scale (Alembic makes it a non-event).
    database_url: str = "sqlite:///./ai_sales_assistant.db"

    # --- LLM provider keys (all optional; the mock provider needs none) ---
    # FREE options (no card): gemini_api_key (aistudio.google.com), groq_api_key
    # (console.groq.com), openrouter_api_key (openrouter.ai), or Ollama (local).
    anthropic_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    groq_api_key: str | None = Field(default=None)
    openrouter_api_key: str | None = Field(default=None)
    deepseek_api_key: str | None = Field(default=None)
    ollama_base_url: str = "http://localhost:11434"
    # Generic OpenAI-compatible endpoint (LM Studio, self-hosted, etc.).
    openai_base_url: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)

    # --- Role -> model routing (see blueprint §4) ---
    # Provider is inferred from the model id prefix by the router.
    model_extraction: str = "mock:extraction"   # cheap tier (Gemini Flash-Lite / DeepSeek in prod)
    model_reasoning: str = "mock:reasoning"      # mid tier
    model_message_gen: str = "mock:message"      # premium (Claude Sonnet 5 in prod)

    # --- Research providers (Phase 2) ---
    exa_api_key: str | None = Field(default=None)

    # --- Security / retention ---
    data_retention_days: int = 90  # GDPR: prospects expire after this window

    # --- Auth ---
    # When true (default), all data endpoints require a valid API key. Set false
    # ONLY for isolated local experiments — never in a deployed environment.
    auth_required: bool = True

    # --- Rate limiting (in-process token bucket; use Redis for multi-worker) ---
    rate_limit_analyze_per_hour: int = 60   # expensive: research + LLM calls
    rate_limit_capture_per_hour: int = 300

    # --- CORS: explicit allowlist in prod; "*" only honored in debug ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
