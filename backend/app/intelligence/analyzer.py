"""Analysis orchestration — the full dual-LLM pipeline (blueprint §5, §6).

    research (off-LinkedIn)  ->  QUARANTINE LLM (untrusted reader, no tools/egress)
                             ->  context builder (validated structured data only)
                             ->  PRIVILEGED LLM (reasoning + brief)
                             ->  persist brief + provenance sources

Stages are streamed to the `stage` column so the dashboard can show live progress.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.db.models import Analysis, JobStatus, Post, Prospect
from app.db.models import CrawledPage as CrawledPageRow  # ORM; distinct from research dataclass
from app.intelligence.context import build_context
from app.intelligence.privileged import run_privileged
from app.intelligence.quarantine import run_quarantine
from app.research.base import WebFindings
from app.research.engine import research_company


async def run_analysis(analysis_id: int) -> None:
    db = SessionLocal()
    try:
        analysis = db.get(Analysis, analysis_id)
        if analysis is None:
            return
        analysis.status = JobStatus.running
        db.commit()

        prospect = db.get(Prospect, analysis.prospect_id)
        posts = sorted(prospect.posts, key=lambda p: p.recency_weight, reverse=True)

        # 1. Off-LinkedIn research (skip cleanly if we have no company to research).
        findings: WebFindings | None = None
        if prospect.company is not None:
            _set_stage(db, analysis, "researching")
            findings = await research_company(
                prospect.company.name, prospect.company.domain
            )

        # 2. Quarantine LLM reads untrusted web text -> structured findings only.
        _set_stage(db, analysis, "quarantine")
        quarantine = await run_quarantine(findings.pages if findings else [])

        # 3. Privileged LLM reasons over validated context (never raw web tokens).
        _set_stage(db, analysis, "reasoning")
        context = build_context(prospect, posts, findings, quarantine)
        result = await run_privileged(context)

        # 4. Persist brief + provenance.
        analysis.result = result.model_dump()
        analysis.opportunity_score = result.opportunity_score
        if findings is not None:
            for page in findings.pages:
                analysis.crawled_pages.append(
                    CrawledPageRow(
                        url=page.url,
                        text=page.text,
                        title=page.title,
                        content_type=page.content_type,
                        byte_size=len(page.text.encode("utf-8")),
                        content_hash=page.content_hash,
                        fetched_at=page.fetched_at,
                    )
                )
        analysis.status = JobStatus.completed
        analysis.stage = "done"
        analysis.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — surface failure onto the job row
        db.rollback()
        analysis = db.get(Analysis, analysis_id)
        if analysis is not None:
            analysis.status = JobStatus.failed
            analysis.error = str(exc)[:2000]
            db.commit()
    finally:
        db.close()


def _set_stage(db, analysis: Analysis, stage: str) -> None:
    analysis.stage = stage
    db.commit()
