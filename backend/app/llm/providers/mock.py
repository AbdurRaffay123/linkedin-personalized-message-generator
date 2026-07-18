"""Keyless deterministic provider.

Lets the whole pipeline run end-to-end in dev/CI without API keys. When asked
for a schema it synthesizes a minimally-valid instance so the orchestration,
persistence, and API layers can be exercised for real. Swap the router config
to a real provider (Anthropic/Gemini) once keys are set.
"""
from __future__ import annotations

from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.llm.base import GenerateOptions, LLMProvider, Message


class MockProvider(LLMProvider):
    name = "mock"

    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel] | None = None,
        options: GenerateOptions | None = None,
    ) -> Any:
        if schema is None:
            last_user = next(
                (m.content for m in reversed(messages) if m.role == "user"), ""
            )
            return f"[mock:{model}] {last_user[:280]}"
        return _synthesize(schema)


def _synthesize(model_cls: type[BaseModel]) -> BaseModel:
    """Build a minimally-valid instance of a Pydantic model from its schema."""
    values: dict[str, Any] = {}
    for field_name, info in model_cls.model_fields.items():
        values[field_name] = _value_for(field_name, info)
    return model_cls(**values)


def _value_for(field_name: str, info: FieldInfo) -> Any:
    annotation = info.annotation
    origin = get_origin(annotation)

    # Optional[...] / unions — pick the first non-None arm.
    if origin is not None and type(None) in get_args(annotation):
        args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = args[0] if args else str
        origin = get_origin(annotation)

    if origin in (list, set, tuple):
        (inner,) = get_args(annotation) or (str,)
        # Respect min_length constraints by emitting one element.
        needs_item = any(
            getattr(m, "min_length", 0) for m in info.metadata
        )
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return [_synthesize(inner)] if needs_item else []
        return [_scalar(inner, field_name)] if needs_item else []

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _synthesize(annotation)

    return _scalar(annotation, field_name)


def _scalar(t: Any, field_name: str) -> Any:
    if t is bool:
        return False
    if t is int:
        return 50
    if t is float:
        return 0.5
    return f"[mock {field_name}]"
