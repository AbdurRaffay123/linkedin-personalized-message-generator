"""The free extraction core (blueprint §3.2): fetch -> Trafilatura (HTML) /
PyMuPDF (PDF). Trafilatura still wins independent main-content benchmarks — we
don't pay per page for what it does well.

JS-heavy / anti-bot pages are a known gap of a plain HTTP fetch; a Playwright
render step plugs in behind `fetch_page` (kept optional so the default install
stays light and browserless).
"""
from __future__ import annotations

import hashlib

import httpx

from app.research.base import CrawledPage

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_MAX_BYTES = 5_000_000  # don't ingest huge assets


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def fetch_page(url: str) -> CrawledPage:
    """Fetch a single URL and extract its main text. Never raises — errors are
    captured on the returned page so a bad URL can't sink the whole crawl."""
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content[:_MAX_BYTES]
            ctype = resp.headers.get("content-type", "text/html").split(";")[0].strip()
    except Exception as exc:  # noqa: BLE001 — normalize transport errors onto the page
        return CrawledPage(url=url, text="", content_hash="", error=str(exc))

    chash = _hash(content)

    if ctype == "application/pdf" or url.lower().endswith(".pdf"):
        text, title = _extract_pdf(content), None
        return CrawledPage(
            url=url, text=text, content_hash=chash, content_type="application/pdf",
            title=title, error=None if text else "empty pdf extraction",
        )

    text, title = _extract_html(content, url)
    return CrawledPage(
        url=url, text=text, content_hash=chash, content_type=ctype, title=title,
        error=None if text else "no main content extracted",
    )


def _extract_html(content: bytes, url: str) -> tuple[str, str | None]:
    import trafilatura

    html = content.decode("utf-8", errors="replace")
    text = trafilatura.extract(
        html, url=url, include_comments=False, include_tables=True, favor_precision=True
    ) or ""
    title = None
    meta = trafilatura.extract_metadata(html)
    if meta is not None:
        title = getattr(meta, "title", None)
    return text.strip(), title


def _extract_pdf(content: bytes) -> str:
    import fitz  # PyMuPDF

    parts: list[str] = []
    with fitz.open(stream=content, filetype="pdf") as doc:
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts).strip()
