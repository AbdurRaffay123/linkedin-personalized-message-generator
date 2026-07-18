"""Ollama provider — 100% local, free forever, private, no account.

Install: https://ollama.com  →  `ollama pull qwen2.5:7b`  (or llama3.2, gemma2).
Runs on your Mac via Metal. Set MODEL_* to e.g. `ollama:qwen2.5:7b`.
Lower quality than cloud models, but unlimited and offline.
"""
from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings
from app.llm.base import GenerateOptions, LLMError, LLMProvider, Message
from app.llm.providers._common import generate_structured


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")

    async def _send(
        self, messages: list[Message], model: str, options: GenerateOptions, json_mode: bool
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": options.temperature,
                "num_predict": options.max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self._base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            return data["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"ollama call failed ({exc}). Is `ollama serve` running and the "
                f"model pulled? Base URL: {self._base_url}"
            ) from exc

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
