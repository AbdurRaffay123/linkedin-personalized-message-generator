"""ORM models — the data model from blueprint §6.

Design constraints baked in here:
- We NEVER store raw LinkedIn HTML server-side (Proxycurl kill-shot avoidance).
  Prospect rows hold only *derived* fields captured client-side.
- `analyses` stores structured, evidence-linked JSON — the moat made queryable.
- `crawled_pages` archives full off-LinkedIn page text + provenance (URL, fetch
  time, content hash) — retained corpus and per-insight provenance in one table.
- `retention_expires_at` supports GDPR/CCPA deletion from day one.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# JSONB on Postgres (compact + indexable), plain JSON on SQLite for local dev.
JSONType = JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    prospects: Mapped[list["Prospect"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    """A hashed API key. The plaintext key is shown once at issue time and never
    stored. Look up is by SHA-256 hash; `prefix` aids identification/rotation."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16))
    name: Mapped[str | None] = mapped_column(String(128), default=None)
    revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    domain: Mapped[str | None] = mapped_column(String(512), index=True, default=None)
    # Firmographics pulled OFF LinkedIn (Exa/enrichment) — structured JSON.
    firmographics: Mapped[dict | None] = mapped_column(JSONType, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    prospects: Mapped[list["Prospect"]] = relationship(back_populates="company")


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), default=None
    )

    # Derived fields only — no raw LinkedIn HTML.
    full_name: Mapped[str] = mapped_column(String(255))
    headline: Mapped[str | None] = mapped_column(String(512), default=None)
    about: Mapped[str | None] = mapped_column(Text, default=None)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), default=None)
    # Richer captured context for ICP/persona inference (section text blocks).
    experience: Mapped[str | None] = mapped_column(Text, default=None)
    education: Mapped[str | None] = mapped_column(Text, default=None)
    skills: Mapped[str | None] = mapped_column(Text, default=None)

    source: Mapped[str] = mapped_column(String(32), default="extension")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    user: Mapped["User"] = relationship(back_populates="prospects")
    company: Mapped["Company | None"] = relationship(back_populates="prospects")
    posts: Mapped[list["Post"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    prospect_id: Mapped[int] = mapped_column(ForeignKey("prospects.id"), index=True)

    content: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(512), default=None)
    engagement: Mapped[dict | None] = mapped_column(JSONType, default=None)  # likes/comments
    recency_weight: Mapped[float] = mapped_column(Float, default=1.0)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    prospect: Mapped["Prospect"] = relationship(back_populates="posts")


class CrawledPage(Base):
    """Archived off-LinkedIn crawled page: full text + provenance.

    This is the moat made queryable AND the retained raw corpus. Only OFF-LinkedIn
    public web content is stored here — never raw LinkedIn HTML (that invariant
    still holds: LinkedIn data stays client-side and ephemeral).
    """

    __tablename__ = "crawled_pages"
    __table_args__ = (
        UniqueConstraint("analysis_id", "url", name="uq_crawled_page_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)

    url: Mapped[str] = mapped_column(String(1024))
    # Full extracted main-content text — the raw corpus the user wants retained.
    text: Mapped[str | None] = mapped_column(Text, default=None)
    title: Mapped[str | None] = mapped_column(String(1024), default=None)
    content_type: Mapped[str] = mapped_column(String(128), default="text/html")
    byte_size: Mapped[int | None] = mapped_column(Integer, default=None)
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["Analysis"] = relationship(back_populates="crawled_pages")


class Analysis(Base):
    """A decision-grade research brief. `result` holds evidence-linked JSON (§6)."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    prospect_id: Mapped[int] = mapped_column(ForeignKey("prospects.id"), index=True)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.pending, index=True
    )
    stage: Mapped[str | None] = mapped_column(String(64), default=None)  # progress UX
    error: Mapped[str | None] = mapped_column(Text, default=None)

    # Structured, evidence-linked result. Shape validated by schemas.analysis.AnalysisResult.
    result: Mapped[dict | None] = mapped_column(JSONType, default=None)
    opportunity_score: Mapped[int | None] = mapped_column(Integer, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    prospect: Mapped["Prospect"] = relationship(back_populates="analyses")
    crawled_pages: Mapped[list["CrawledPage"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)

    body: Mapped[str] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(64), default=None)
    length: Mapped[str | None] = mapped_column(String(64), default=None)
    goal: Mapped[str | None] = mapped_column(String(128), default=None)
    model_used: Mapped[str | None] = mapped_column(String(128), default=None)
    variant_of: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id"), default=None
    )
    edited_by_user: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["Analysis"] = relationship(back_populates="messages")
