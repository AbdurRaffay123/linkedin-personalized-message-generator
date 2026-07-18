"""LLM provider abstraction (blueprint §4).

Route by ROLE, not by hardcoded model name. Normalize structured output across
providers behind one JSON-schema layer so business logic never sees a vendor.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class GenerateOptions:
    max_tokens: int = 2048
    temperature: float = 0.7
    extra: dict[str, Any] = field(default_factory=dict)


class LLMError(RuntimeError):
    """Raised on provider/transport failures after retries."""


class LLMProvider(abc.ABC):
    """One method, two modes: free-form text, or schema-validated object."""

    #: Human-readable id, e.g. "anthropic", "mock".
    name: str = "provider"

    @abc.abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel] | None = None,
        options: GenerateOptions | None = None,
    ) -> Any:
        """Return validated `schema` instance when given, else the raw text string."""
        raise NotImplementedError
