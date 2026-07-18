"""HTTP surface: health, capture, async analyze + poll (blueprint §6)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
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


_DEV_EMAIL = "dev@local"


def _dev_user(db: Session) -> User:
    """MVP single-user shim. Replaced by real auth in hardening (Phase 7)."""
    user = db.scalar(select(User).where(User.email == _DEV_EMAIL))
    if user is None:
        user = User(email=_DEV_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}


@router.post("/prospects/capture", response_model=ProspectOut, status_code=201)
def capture(payload: CaptureIn, db: Session = Depends(get_db)) -> Prospect:
    """Passive extension posts derived fields only. No raw HTML stored."""
    user = _dev_user(db)

    company = None
    if payload.company is not None:
        company = db.scalar(
            select(Company).where(Company.name == payload.company.name)
        )
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


@router.get("/prospects", response_model=list[ProspectOut])
def list_prospects(db: Session = Depends(get_db)) -> list[Prospect]:
    """Most-recent-first list for the dashboard (current dev user)."""
    user = _dev_user(db)
    return list(
        db.scalars(
            select(Prospect)
            .where(Prospect.user_id == user.id)
            .order_by(Prospect.captured_at.desc())
        )
    )


@router.get("/prospects/{prospect_id}", response_model=ProspectOut)
def get_prospect(prospect_id: int, db: Session = Depends(get_db)) -> Prospect:
    prospect = db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(404, "prospect not found")
    return prospect


@router.get("/prospects/{prospect_id}/analyses", response_model=list[AnalysisOut])
def list_analyses(prospect_id: int, db: Session = Depends(get_db)) -> list[Analysis]:
    if db.get(Prospect, prospect_id) is None:
        raise HTTPException(404, "prospect not found")
    return list(
        db.scalars(
            select(Analysis)
            .where(Analysis.prospect_id == prospect_id)
            .order_by(Analysis.created_at.desc())
        )
    )


@router.get("/analyses/{analysis_id}/messages", response_model=list[MessageOut])
def list_messages(analysis_id: int, db: Session = Depends(get_db)) -> list[Message]:
    if db.get(Analysis, analysis_id) is None:
        raise HTTPException(404, "analysis not found")
    return list(
        db.scalars(
            select(Message)
            .where(Message.analysis_id == analysis_id)
            .order_by(Message.created_at.desc())
        )
    )


@router.post(
    "/prospects/{prospect_id}/analyze",
    response_model=AnalyzeAccepted,
    status_code=202,
)
def analyze(
    prospect_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalyzeAccepted:
    prospect = db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(404, "prospect not found")

    analysis = Analysis(prospect_id=prospect_id, status=JobStatus.pending)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    background.add_task(_run, analysis.id)
    return AnalyzeAccepted(analysis_id=analysis.id, status=analysis.status)


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    return analysis


@router.post(
    "/analyses/{analysis_id}/messages", response_model=MessageOut, status_code=201
)
async def create_message(
    analysis_id: int, payload: MessageIn, db: Session = Depends(get_db)
) -> Message:
    """Draft a grounded outreach message from a completed brief. Human reviews
    before sending — we never auto-send (§5 human-in-the-loop gate)."""
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
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


def _run(analysis_id: int) -> None:
    """Bridge sync BackgroundTasks to the async analyzer."""
    import asyncio

    asyncio.run(run_analysis(analysis_id))
