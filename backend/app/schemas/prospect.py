"""Request/response schemas for prospect capture and analysis endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import JobStatus
from app.schemas.analysis import AnalysisResult


class PostIn(BaseModel):
    content: str
    url: str | None = None
    engagement: dict | None = None
    posted_at: datetime | None = None


class CompanyIn(BaseModel):
    name: str
    domain: str | None = None


class CaptureIn(BaseModel):
    """What the passive extension POSTs — derived fields only, never raw HTML."""

    full_name: str
    headline: str | None = None
    about: str | None = None
    linkedin_url: str | None = None
    company: CompanyIn | None = None
    posts: list[PostIn] = Field(default_factory=list)


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    domain: str | None


class ProspectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    headline: str | None
    linkedin_url: str | None
    captured_at: datetime
    company: CompanyOut | None = None


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prospect_id: int
    status: JobStatus
    stage: str | None
    error: str | None
    result: AnalysisResult | None
    opportunity_score: int | None
    created_at: datetime
    completed_at: datetime | None


class AnalyzeAccepted(BaseModel):
    analysis_id: int
    status: JobStatus


class MessageIn(BaseModel):
    tone: str = "warm"
    length: str = "short"
    goal: str = "book a short call"


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    body: str
    tone: str | None
    length: str | None
    goal: str | None
    model_used: str | None
    edited_by_user: bool
    created_at: datetime
