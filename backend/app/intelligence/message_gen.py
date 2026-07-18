"""Message generation (blueprint §5 last mile, §6 AI rules).

The commoditized last mile — but the one place NOT to cheap out on the model
(routed to `message_gen`, i.e. Claude Sonnet 5 in prod). It is grounded strictly
in the evidence-linked brief, so it can't invent pain points the research didn't
find. Output is a DRAFT only: a human reviews before anything is sent (§5 gate).
"""
from __future__ import annotations

from app.llm.base import GenerateOptions, Message
from app.llm.router import router
from app.schemas.analysis import AnalysisResult

# The AI rules, promoted from the blueprint. Evidence-grounding is enforced by
# feeding only the structured brief — the model has nothing else to draw from.
_SYSTEM = """You write short, human first-touch outreach for a founder/seller.

Hard rules:
- Ground every specific claim in the provided brief's evidence. Invent nothing.
- No fake compliments, no generic sales language, no manufactured urgency.
- Prefer one specific, verifiable observation as the opener.
- Founder-to-founder tone: natural, direct, low-pressure.
- Respect the requested tone, length, and goal.
- This is a DRAFT for human review — do not include placeholders like [Name].

Return ONLY the message text."""


async def generate_message(
    brief: AnalysisResult,
    prospect_name: str,
    *,
    tone: str = "warm",
    length: str = "short",
    goal: str = "book a short call",
) -> str:
    signals = "; ".join(f"{s.type}: {s.detail}" for s in brief.signals) or "none"
    pains = "; ".join(h.hypothesis for h in brief.pain_hypotheses) or "none"
    user = (
        f"Prospect: {prospect_name}\n"
        f"Recommended angle: {brief.recommended_angle}\n"
        f"Signals: {signals}\n"
        f"Pain hypotheses: {pains}\n\n"
        f"Write a {length}, {tone} message whose goal is to {goal}."
    )
    return await router.generate(
        "message_gen",
        [Message("system", _SYSTEM), Message("user", user)],
        options=GenerateOptions(temperature=0.7, max_tokens=512),
    )
