"""Research-engine tests.

- Discovery/enrichment run on keyless mocks.
- The crawl+extract path is exercised against a real page behind a network
  marker so CI can skip it offline.
"""
from __future__ import annotations

import pytest

from app.research.engine import research_company
from app.research.crawl import fetch_page


async def test_research_company_mock():
    findings = await research_company("Acme Robotics", domain="example.com", max_pages=2)
    assert findings.company_name == "Acme Robotics"
    assert findings.firmographics is not None
    # Provenance rows are shaped for the `sources` table.
    for src in findings.sources:
        assert set(src) == {"url", "fetched_at", "content_hash"}


@pytest.mark.network
async def test_fetch_real_page():
    page = await fetch_page("https://example.com")
    assert page.ok
    assert "example" in page.text.lower()
    assert len(page.content_hash) == 64
