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
    anthropic_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    deepseek_api_key: str | None = Field(default=None)
    ollama_base_url: str = "http://localhost:11434"

    # --- Role -> model routing (see blueprint §4) ---
    # Provider is inferred from the model id prefix by the router.
    model_extraction: str = "mock:extraction"   # cheap tier (Gemini Flash-Lite / DeepSeek in prod)
    model_reasoning: str = "mock:reasoning"      # mid tier
    model_message_gen: str = "mock:message"      # premium (Claude Sonnet 5 in prod)

    # --- Research providers (Phase 2) ---
    exa_api_key: str | None = Field(default=None)

    # --- Security / retention ---
    data_retention_days: int = 90  # GDPR: prospects expire after this window


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
