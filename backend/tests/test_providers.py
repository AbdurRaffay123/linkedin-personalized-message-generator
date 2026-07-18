"""Free-provider wiring: router construction + request/response handling.

HTTP is mocked, so these run offline and without any API keys — they verify the
request shape, response parsing, and structured validate-and-retry path.
"""
from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from app.llm.base import GenerateOptions, Message
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.router import _build_provider


class Tiny(BaseModel):
    label: str
    score: int


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    response_data = None
    last = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        _FakeClient.last = {"url": url, "json": json, "headers": headers}
        return _FakeResponse(_FakeClient.response_data)


@pytest.fixture(autouse=True)
def _mock_httpx(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)


def test_router_builds_free_providers():
    assert _build_provider("gemini").name == "gemini"
    assert _build_provider("ollama").name == "ollama"
    assert _build_provider("groq").name == "groq"
    assert _build_provider("openrouter").name == "openrouter"


async def test_openai_compatible_text():
    _FakeClient.response_data = {"choices": [{"message": {"content": "hi there"}}]}
    p = OpenAICompatibleProvider("groq", "https://api.groq.com/openai/v1", "k")
    out = await p.generate([Message("user", "hello")], model="llama-3.3-70b")
    assert out == "hi there"
    assert _FakeClient.last["json"]["model"] == "llama-3.3-70b"
    assert _FakeClient.last["headers"]["Authorization"] == "Bearer k"


async def test_openai_compatible_structured():
    _FakeClient.response_data = {
        "choices": [{"message": {"content": '{"label": "ok", "score": 7}'}}]
    }
    p = OpenAICompatibleProvider("groq", "https://api.groq.com/openai/v1", "k")
    out = await p.generate(
        [Message("user", "give me one")], model="m", schema=Tiny,
        options=GenerateOptions(),
    )
    assert isinstance(out, Tiny)
    assert out.label == "ok" and out.score == 7
    assert _FakeClient.last["json"]["response_format"] == {"type": "json_object"}


async def test_gemini_structured_parsing():
    _FakeClient.response_data = {
        "candidates": [{"content": {"parts": [{"text": '{"label":"g","score":3}'}]}}]
    }
    p = GeminiProvider(api_key="free-key")
    out = await p.generate([Message("user", "x")], model="gemini-2.0-flash", schema=Tiny)
    assert isinstance(out, Tiny)
    assert out.label == "g" and out.score == 3
    assert _FakeClient.last["json"]["generationConfig"]["responseMimeType"] == "application/json"
