"""Context builder (blueprint §6 pipeline).

Merges the trusted person data (from the extension) with the VALIDATED structured
findings from the Quarantine LLM. The privileged reasoner sees only this — never
raw untrusted web tokens.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.db.models import Post, Prospect
from app.research.base import WebFindings
from app.schemas.analysis import QuarantineFindings


@dataclass
class ProspectContext:
    full_name: str
    headline: str | None
    about: str | None
    company_name: str | None
    company_domain: str | None
    recent_posts: list[str]
    firmographics: dict | None
    # Already-structured, already-validated — safe to hand to the privileged LLM.
    quarantine: QuarantineFindings

    def to_prompt(self) -> str:
        lines = [
            f"Prospect: {self.full_name}",
            f"Headline: {self.headline or 'n/a'}",
            f"About: {self.about or 'n/a'}",
            f"Company: {self.company_name or 'n/a'} ({self.company_domain or 'no domain'})",
        ]
        if self.recent_posts:
            lines.append("Recent posts:")
            lines += [f"  - {p[:400]}" for p in self.recent_posts]
        if self.firmographics:
            lines.append(f"Firmographics: {self.firmographics}")
        lines.append("\nStructured web findings (validated, from quarantined reader):")
        for s in self.quarantine.signals:
            lines.append(f"  signal[{s.type}] {s.detail} (src={s.source_url}, conf={s.confidence})")
        for h in self.quarantine.pain_hypotheses:
            lines.append(f"  pain: {h.hypothesis} | evidence={h.evidence} (conf={h.confidence})")
        return "\n".join(lines)


def build_context(
    prospect: Prospect,
    posts: list[Post],
    findings: WebFindings | None,
    quarantine: QuarantineFindings,
) -> ProspectContext:
    return ProspectContext(
        full_name=prospect.full_name,
        headline=prospect.headline,
        about=prospect.about,
        company_name=prospect.company.name if prospect.company else (
            findings.company_name if findings else None
        ),
        company_domain=prospect.company.domain if prospect.company else (
            findings.domain if findings else None
        ),
        recent_posts=[p.content for p in posts],
        firmographics=findings.firmographics if findings else None,
        quarantine=quarantine,
    )
