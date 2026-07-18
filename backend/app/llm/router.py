"""Role-based LLM router (blueprint §4).

Business logic asks for a ROLE ("extraction" | "reasoning" | "message_gen").
Config maps role -> model id of the form "provider:model". The router lazily
instantiates the matching provider and normalizes structured output for all.

Swapping Sonnet<->Haiku for writing, or DeepSeek<->Gemini for extraction, is a
config change — no business logic touched.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.config import settings
from app.llm.base import GenerateOptions, LLMError, LLMProvider, Message

Role = Literal["extraction", "reasoning", "message_gen"]


class LLMRouter:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._role_models: dict[str, str] = {
            "extraction": settings.model_extraction,
            "reasoning": settings.model_reasoning,
            "message_gen": settings.model_message_gen,
        }

    def _provider(self, key: str) -> LLMProvider:
        if key not in self._providers:
            self._providers[key] = _build_provider(key)
        return self._providers[key]

    @staticmethod
    def _split(model_id: str) -> tuple[str, str]:
        if ":" not in model_id:
            raise LLMError(
                f"model id '{model_id}' must be 'provider:model' (e.g. 'anthropic:claude-sonnet-5')"
            )
        provider_key, model = model_id.split(":", 1)
        return provider_key, model

    async def generate(
        self,
        role: Role,
        messages: list[Message],
        *,
        schema: type[BaseModel] | None = None,
        options: GenerateOptions | None = None,
    ) -> Any:
        model_id = self._role_models[role]
        provider_key, model = self._split(model_id)
        provider = self._provider(provider_key)
        return await provider.generate(
            messages, model=model, schema=schema, options=options
        )


def _build_provider(key: str) -> LLMProvider:
    if key == "mock":
        from app.llm.providers.mock import MockProvider

        return MockProvider()
    if key == "anthropic":
        from app.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    # Gemini / DeepSeek / Ollama providers plug in here (same interface).
    raise LLMError(f"unknown or unconfigured LLM provider '{key}'")


# Module-level singleton — cheap; providers instantiate lazily on first use.
router = LLMRouter()
