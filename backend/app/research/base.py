"""Research-engine data structures and provider interfaces (blueprint §2, §3.2).

Everything the research engine produces carries provenance (URL + fetch time +
content hash) so every downstream insight is traceable — the moat, made queryable.

IMPORTANT: All company/firmographic data comes from OFF LinkedIn. Nothing in this
module touches LinkedIn's authenticated surface.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SearchHit:
    url: str
    title: str | None = None
    snippet: str | None = None
    score: float | None = None


@dataclass
class CrawledPage:
    url: str
    text: str
    content_hash: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_type: str = "text/html"
    title: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


@dataclass
class WebFindings:
    """Structured, provenance-bearing output of the research engine.

    `pages` is UNTRUSTED web text — it must only ever be handed to the Quarantine
    LLM (Phase 3, §5), never to a tool-bearing/privileged model.
    """

    company_name: str
    domain: str | None
    pages: list[CrawledPage] = field(default_factory=list)
    firmographics: dict | None = None

    @property
    def sources(self) -> list[dict]:
        """Provenance rows ready to persist into the `sources` table."""
        return [
            {"url": p.url, "fetched_at": p.fetched_at, "content_hash": p.content_hash}
            for p in self.pages
            if p.ok
        ]


class DiscoveryProvider(abc.ABC):
    """Find candidate URLs for a company (semantic web search)."""

    name: str = "discovery"

    @abc.abstractmethod
    async def find(self, query: str, *, limit: int = 5) -> list[SearchHit]: ...


class EnrichmentProvider(abc.ABC):
    """Name/domain -> firmographics, from OFF-LinkedIn public-data sources."""

    name: str = "enrichment"

    @abc.abstractmethod
    async def enrich(self, company_name: str, domain: str | None) -> dict: ...
