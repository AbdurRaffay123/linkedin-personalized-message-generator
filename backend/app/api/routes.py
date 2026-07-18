"""HTTP surface: health, capture, async analyze + poll, GDPR deletion.

All data endpoints require an authenticated user (see core.auth) and enforce
ownership: a user can only see/act on their own prospects. Unknown-vs-forbidden
is collapsed to 404 so ids don't leak across tenants.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_user
from app.core.ratelimit import limit_analyze, limit_capture
from app.db.base import get_db
from app.db.models import (
    Analysis,
    Company,
    JobStatus,
    Message,
    Post,
    Prospect,
    User,
    utcnow,
)
from app.intelligence.analyzer import run_analysis
from app.intelligence.message_gen import generate_message
from app.schemas.analysis import AnalysisResult
from app.schemas.prospect import (
    AnalysisOut,
    AnalyzeAccepted,
    CaptureIn,
    MessageIn,
    MessageOut,
    ProspectOut,
)

router = APIRouter()


# --- ownership helpers -------------------------------------------------------

def _owned_prospect(prospect_id: int, user: User, db: Session) -> Prospect:
    prospect = db.get(Prospect, prospect_id)
    if prospect is None or prospect.user_id != user.id:
        raise HTTPException(404, "prospect not found")
    return prospect


def _owned_analysis(analysis_id: int, user: User, db: Session) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    prospect = db.get(Prospect, analysis.prospect_id)
    if prospect is None or prospect.user_id != user.id:
        raise HTTPException(404, "analysis not found")
    return analysis


# --- health (unauthenticated) ------------------------------------------------

@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}


# --- capture -----------------------------------------------------------------

@router.post("/prospects/capture", response_model=ProspectOut, status_code=201)
def capture(
    payload: CaptureIn,
    db: Session = Depends(get_db),
    user: User = Depends(limit_capture),
) -> Prospect:
    """Passive extension posts derived fields only. No raw HTML stored."""
    company = None
    if payload.company is not None:
        company = db.scalar(select(Company).where(Company.name == payload.company.name))
        if company is None:
            company = Company(name=payload.company.name, domain=payload.company.domain)
            db.add(company)
            db.flush()

    prospect = Prospect(
        user_id=user.id,
        company_id=company.id if company else None,
        full_name=payload.full_name,
        headline=payload.headline,
        about=payload.about,
        linkedin_url=payload.linkedin_url,
        experience=payload.experience,
        education=payload.education,
        skills=payload.skills,
        retention_expires_at=utcnow() + timedelta(days=settings.data_retention_days),
    )
    for p in payload.posts:
        prospect.posts.append(
            Post(content=p.content, url=p.url, engagement=p.engagement, posted_at=p.posted_at)
        )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return prospect


# --- reads (scoped to the user) ----------------------------------------------

@router.get("/prospects", response_model=list[ProspectOut])
def list_prospects(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Prospect]:
    return list(
        db.scalars(
            select(Prospect)
            .where(Prospect.user_id == user.id)
            .order_by(Prospect.captured_at.desc())
        )
    )


@router.get("/prospects/{prospect_id}", response_model=ProspectOut)
def get_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Prospect:
    return _owned_prospect(prospect_id, user, db)


@router.get("/prospects/{prospect_id}/analyses", response_model=list[AnalysisOut])
def list_analyses(
    prospect_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Analysis]:
    _owned_prospect(prospect_id, user, db)
    return list(
        db.scalars(
            select(Analysis)
            .where(Analysis.prospect_id == prospect_id)
            .order_by(Analysis.created_at.desc())
        )
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Analysis:
    return _owned_analysis(analysis_id, user, db)


@router.get("/analyses/{analysis_id}/messages", response_model=list[MessageOut])
def list_messages(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Message]:
    _owned_analysis(analysis_id, user, db)
    return list(
        db.scalars(
            select(Message)
            .where(Message.analysis_id == analysis_id)
            .order_by(Message.created_at.desc())
        )
    )


# --- analyze (rate-limited) --------------------------------------------------

@router.post(
    "/prospects/{prospect_id}/analyze", response_model=AnalyzeAccepted, status_code=202
)
def analyze(
    prospect_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(limit_analyze),
) -> AnalyzeAccepted:
    _owned_prospect(prospect_id, user, db)
    analysis = Analysis(prospect_id=prospect_id, status=JobStatus.pending)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    background.add_task(_run, analysis.id)
    return AnalyzeAccepted(analysis_id=analysis.id, status=analysis.status)


@router.post(
    "/analyses/{analysis_id}/messages", response_model=MessageOut, status_code=201
)
async def create_message(
    analysis_id: int,
    payload: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    """Draft a grounded outreach message from a completed brief. Human reviews
    before sending — we never auto-send (§5 human-in-the-loop gate)."""
    analysis = _owned_analysis(analysis_id, user, db)
    if analysis.status != JobStatus.completed or analysis.result is None:
        raise HTTPException(409, "analysis is not completed")

    brief = AnalysisResult.model_validate(analysis.result)
    prospect = db.get(Prospect, analysis.prospect_id)
    body = await generate_message(
        brief, prospect.full_name, tone=payload.tone, length=payload.length,
        goal=payload.goal,
    )

    message = Message(
        analysis_id=analysis_id, body=body, tone=payload.tone, length=payload.length,
        goal=payload.goal, model_used=settings.model_message_gen,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


# --- GDPR / right-to-erasure -------------------------------------------------

@router.delete("/prospects/{prospect_id}", status_code=204)
def delete_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a prospect and everything derived from it (cascade)."""
    prospect = _owned_prospect(prospect_id, user, db)
    db.delete(prospect)
    db.commit()


@router.delete("/me/data", status_code=204)
def erase_my_data(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    """Right-to-erasure: purge all of the caller's prospects (and cascades)."""
    for prospect in db.scalars(select(Prospect).where(Prospect.user_id == user.id)):
        db.delete(prospect)
    db.commit()


def _run(analysis_id: int) -> None:
    """Bridge sync BackgroundTasks to the async analyzer."""
    import asyncio

    asyncio.run(run_analysis(analysis_id))
