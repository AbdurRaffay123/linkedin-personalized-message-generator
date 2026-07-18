"""Research engine orchestration (blueprint Phase 2).

Given a company name (+ optional domain), produce clean, structured, provenance-
bearing web findings — entirely OFF LinkedIn:

    discover candidate URLs  ->  crawl + extract (concurrently)  ->  enrich

The output `WebFindings.pages` is UNTRUSTED and must only reach the Quarantine
LLM in Phase 3, never a tool-bearing model.
"""
from __future__ import annotations

import asyncio

from app.research.base import WebFindings
from app.research.crawl import fetch_page
from app.research.discovery import get_discovery
from app.research.enrichment import get_enrichment


async def research_company(
    company_name: str,
    domain: str | None = None,
    *,
    max_pages: int = 4,
) -> WebFindings:
    discovery = get_discovery()
    enrichment = get_enrichment()

    # 1. Discover candidate URLs. Seed with the known domain if we have one.
    query = f"{company_name} official company website" + (f" {domain}" if domain else "")
    hits = await discovery.find(query, limit=max_pages)

    urls: list[str] = []
    if domain:
        urls.append(domain if domain.startswith("http") else f"https://{domain}")
    urls.extend(h.url for h in hits)
    # De-dup, preserve order, cap.
    seen: set[str] = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))][:max_pages]

    # 2. Crawl concurrently; failures are captured per-page, not fatal.
    pages = await asyncio.gather(*(fetch_page(u) for u in urls)) if urls else []

    # 3. Enrich (off-LinkedIn firmographics).
    firmographics = await enrichment.enrich(company_name, domain)

    return WebFindings(
        company_name=company_name,
        domain=domain,
        pages=[p for p in pages if p.ok],
        firmographics=firmographics,
    )
