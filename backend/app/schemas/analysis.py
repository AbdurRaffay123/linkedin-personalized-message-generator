"""Evidence-linked analysis schemas — the structural enforcement of "no invented
problems" (blueprint §6). Every claim must carry evidence + source + confidence.

This same schema is what the Quarantine LLM is forced to emit (§5): free-form
instructions cannot survive a strict structured-output boundary.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Signal(BaseModel):
    type: str = Field(description="e.g. hiring, funding, job_change, tech_shift, post")
    detail: str
    source_url: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class PainHypothesis(BaseModel):
    hypothesis: str
    # Evidence is mandatory and non-empty — the model literally cannot assert a
    # pain point without attaching supporting quotes/lines.
    evidence: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ShouldReachOut(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class QuarantineFindings(BaseModel):
    """What the Quarantine LLM is forced to emit when reading untrusted web text.

    Because this is a strict structured-output boundary, no free-form instruction
    embedded in a malicious page can survive as anything other than inert data in
    one of these typed fields (blueprint §5).
    """

    signals: list[Signal] = Field(default_factory=list)
    pain_hypotheses: list[PainHypothesis] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """The structured brief stored in Analysis.result."""

    # Who they are + how they think — inferred from role, background, and writing.
    # Grounds the outreach in their actual mindset and ICP fit.
    persona_summary: str = ""
    signals: list[Signal] = Field(default_factory=list)
    pain_hypotheses: list[PainHypothesis] = Field(default_factory=list)
    recommended_angle: str
    should_reach_out: ShouldReachOut
    opportunity_score: int = Field(ge=0, le=100)
