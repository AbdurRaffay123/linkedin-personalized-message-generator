"""Google Gemini provider — GENEROUS FREE TIER, no credit card.

Get a free key at https://aistudio.google.com/apikey and set GEMINI_API_KEY.
Recommended free models: gemini-2.0-flash (fast, capable) or gemini-2.0-flash-lite.

Uses the REST API via httpx (no extra SDK dependency). Structured output goes
through JSON mode + validate-and-retry (see _common).
"""
from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings
from app.llm.base import GenerateOptions, LLMError, LLMProvider, Message
from app.llm.providers._common import generate_structured

_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.gemini_api_key

    async def _send(
        self, messages: list[Message], model: str, options: GenerateOptions, json_mode: bool
    ) -> str:
        if not self._api_key:
            raise LLMError("GEMINI_API_KEY not set (free key: aistudio.google.com/apikey)")

        system = "\n\n".join(m.content for m in messages if m.role == "system")
        contents = [
            {
                "role": "model" if m.role == "assistant" else "user",
                "parts": [{"text": m.content}],
            }
            for m in messages
            if m.role in ("user", "assistant")
        ]
        gen_config: dict[str, Any] = {
            "temperature": options.temperature,
            "maxOutputTokens": options.max_tokens,
        }
        if json_mode:
            gen_config["responseMimeType"] = "application/json"

        body: dict[str, Any] = {"contents": contents, "generationConfig": gen_config}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"{_BASE}/models/{model}:generateContent?key={self._api_key}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"gemini call failed: {exc}") from exc

    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel] | None = None,
        options: GenerateOptions | None = None,
    ) -> Any:
        opts = options or GenerateOptions()
        if schema is None:
            return await self._send(messages, model, opts, False)
        return await generate_structured(
            lambda msgs, jm: self._send(msgs, model, opts, jm), messages, schema, opts
        )
