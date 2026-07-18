"""Firmographic enrichment — name/domain -> company facts (blueprint §3.2).

Pulled from OFF-LinkedIn public-data sources (People Data Labs / Coresignal /
Hunter in prod). Keyless Mock keeps the pipeline runnable. Do NOT build on
Clearbit (sunset) or Proxycurl-style fake-account vendors (dead/radioactive).
"""
from __future__ import annotations

from app.research.base import EnrichmentProvider


class MockEnrichment(EnrichmentProvider):
    name = "mock"

    async def enrich(self, company_name: str, domain: str | None) -> dict:
        return {
            "name": company_name,
            "domain": domain,
            "employee_range": None,
            "industry": None,
            "source": "mock",
        }


def get_enrichment() -> EnrichmentProvider:
    # Real providers plug in here, selected by key presence (same pattern as discovery).
    return MockEnrichment()
