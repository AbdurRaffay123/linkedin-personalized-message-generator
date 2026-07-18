"""Anthropic provider — message generation and reasoning (blueprint §4).

Structured output uses strict tool use: we expose a single tool whose input
schema is the target Pydantic model's JSON schema and force the model to call
it, then validate the tool input. This hits ~99.8%+ schema compliance.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.config import settings
from app.llm.base import GenerateOptions, LLMError, LLMProvider, Message

_STRUCTURED_TOOL = "emit_structured_output"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.anthropic_api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise LLMError("ANTHROPIC_API_KEY is not set")
            from anthropic import AsyncAnthropic  # lazy import

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel] | None = None,
        options: GenerateOptions | None = None,
    ) -> Any:
        opts = options or GenerateOptions()
        client = self._get_client()

        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        convo = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        try:
            if schema is None:
                resp = await client.messages.create(
                    model=model,
                    system=system,
                    messages=convo,
                    max_tokens=opts.max_tokens,
                    temperature=opts.temperature,
                )
                return "".join(
                    b.text for b in resp.content if getattr(b, "type", None) == "text"
                )

            tool = {
                "name": _STRUCTURED_TOOL,
                "description": "Return the result strictly matching the schema.",
                "input_schema": schema.model_json_schema(),
            }
            resp = await client.messages.create(
                model=model,
                system=system,
                messages=convo,
                max_tokens=opts.max_tokens,
                temperature=opts.temperature,
                tools=[tool],
                tool_choice={"type": "tool", "name": _STRUCTURED_TOOL},
            )
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    return schema.model_validate(block.input)
            raise LLMError("model did not return a structured tool call")
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 — normalize provider errors
            raise LLMError(f"anthropic call failed: {exc}") from exc
