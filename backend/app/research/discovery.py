"""Company discovery — semantic web search (blueprint §3.2).

Exa is the pragmatic default in prod (~$7/1k, 20k free/mo). A keyless Mock
provider keeps the pipeline runnable in dev/CI. Selection is by config/key
presence, so swapping is a config change, not a code change.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.research.base import DiscoveryProvider, SearchHit


class MockDiscovery(DiscoveryProvider):
    name = "mock"

    async def find(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        # Deterministic stand-in so the crawl/analyze path runs without keys.
        slug = query.lower().split()[0] if query.split() else "example"
        return [
            SearchHit(
                url=f"https://example.com/{slug}",
                title=f"{query} — official site (mock)",
                snippet="Mock discovery result.",
                score=0.9,
            )
        ][:limit]


class ExaDiscovery(DiscoveryProvider):
    name = "exa"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.exa_api_key

    async def find(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        if not self._api_key:
            raise RuntimeError("EXA_API_KEY not set")
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": self._api_key, "content-type": "application/json"},
                json={"query": query, "numResults": limit, "type": "auto"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchHit(
                url=r["url"],
                title=r.get("title"),
                snippet=r.get("text") or r.get("snippet"),
                score=r.get("score"),
            )
            for r in data.get("results", [])
        ]


def get_discovery() -> DiscoveryProvider:
    """Pick the provider by available config. Exa if a key is present, else mock."""
    if settings.exa_api_key:
        return ExaDiscovery()
    return MockDiscovery()
