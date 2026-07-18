"""OpenAI-compatible chat provider — one class, many FREE backends.

The `/chat/completions` shape is a de-facto standard, so this single provider
covers several free options:
  - Groq        (https://console.groq.com — free, very fast, Llama 3.3 70B)
  - OpenRouter  (https://openrouter.ai — free `:free` model variants)
  - DeepSeek    (https://platform.deepseek.com — cheap, generous)
  - LM Studio / any local OpenAI-compatible server

The router constructs one with the right base_url + key per provider id.
"""
from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from app.llm.base import GenerateOptions, LLMError, LLMProvider, Message
from app.llm.providers._common import generate_structured


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, name: str, base_url: str | None, api_key: str | None):
        self.name = name
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key

    async def _send(
        self, messages: list[Message], model: str, options: GenerateOptions, json_mode: bool
    ) -> str:
        if not self._base_url:
            raise LLMError(f"{self.name}: base URL not configured")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"]
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"{self.name} call failed: {exc}") from exc

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
