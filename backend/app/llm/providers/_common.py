"""Shared helpers for providers without native strict tool use.

Gemini / Groq / OpenRouter / DeepSeek / Ollama all reliably return JSON when
asked (and given a JSON mode flag), but none guarantee schema compliance the way
Anthropic strict tool use does. So we prompt with the schema, parse, validate,
and retry once with the error — the blueprint's "validate-and-retry" wrapper (§4).
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm.base import GenerateOptions, LLMError, Message

# A provider supplies this: given messages and whether to request JSON mode,
# return the model's raw text response.
SendFn = Callable[[list[Message], bool], Awaitable[str]]


def extract_json(text: str) -> Any:
    """Pull a JSON object out of a model response (tolerates code fences/prose)."""
    s = text.strip()
    if s.startswith("```"):
        # Strip a ```json … ``` fence.
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end > start:
            return json.loads(s[start : end + 1])
        raise


async def generate_structured(
    send: SendFn,
    messages: list[Message],
    schema: type[BaseModel],
    options: GenerateOptions | None = None,  # noqa: ARG001 — accepted for symmetry
    *,
    max_retries: int = 1,
) -> BaseModel:
    schema_json = json.dumps(schema.model_json_schema())
    convo = [
        *messages,
        Message(
            "user",
            "Respond with ONLY a single JSON object — no prose, no code fence — "
            f"that validates against this JSON Schema:\n{schema_json}",
        ),
    ]
    last_err: Exception | None = None
    for _ in range(max_retries + 1):
        text = await send(convo, True)
        try:
            return schema.model_validate(extract_json(text))
        except (ValidationError, json.JSONDecodeError) as exc:
            last_err = exc
            convo = [
                *convo,
                Message("assistant", text),
                Message(
                    "user",
                    f"That did not validate ({exc}). Return corrected JSON only.",
                ),
            ]
    raise LLMError(f"structured output failed schema validation: {last_err}")
