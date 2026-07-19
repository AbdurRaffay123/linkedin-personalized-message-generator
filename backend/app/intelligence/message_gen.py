"""Message generation (blueprint §5 last mile, §6 AI rules).

The commoditized last mile — but the one place NOT to cheap out on the model
(routed to `message_gen`). It is grounded strictly in the evidence-linked brief,
so it can't invent pain points the research didn't find. Output is a DRAFT only:
a human reviews before anything is sent (§5 gate).

Philosophy: this writes the FIRST touch of a long-term relationship, not a cold
pitch. The goal of message one is to earn a reply and start a genuine
conversation — never to close, book, or pitch. Trust compounds; the ask comes
much later, if at all.
"""
from __future__ import annotations

from app.llm.base import GenerateOptions, Message
from app.llm.router import router
from app.schemas.analysis import AnalysisResult

# The AI rules, promoted from the blueprint. Evidence-grounding is enforced by
# feeding only the structured brief — the model has nothing else to draw from.
_SYSTEM = """You write the FIRST message of what should become a long-term
professional relationship — not a cold sales pitch. You are writing on behalf of
a founder/seller who plays the long game: they want to earn trust and start a
real conversation, not extract a meeting from a stranger.

Think like a thoughtful peer reaching out to someone they respect. The entire
job of this first message is to earn a genuine reply. Nothing else.

How to write it:
- Open with ONE specific, verifiable observation about them or their work —
  something only someone who actually looked would say. This proves you see them
  as a person, not a lead.
- Speak to their psychology and the pain that actually matters to them, but
  frame it as curiosity or shared perspective, not a diagnosis you're selling
  against.
- Give before you take: offer a genuine insight, a relevant angle, or honest
  admiration for a specific decision they made. Lead with value, not need.
- Make the "ask" tiny and optional — an invitation to swap notes or continue the
  thread, NOT a demand for a call, demo, or calendar booking. A reply IS the win.
  Even when a call is the stated goal, soften it to "worth a conversation
  sometime?" rather than "can we book 15 minutes?"
- Sound like a human typed it in one sitting: warm, direct, a little informal,
  low-pressure. Short. No corporate voice.

Hard rules:
- Ground every specific claim in the provided brief's evidence. Invent nothing.
- No fake compliments, no generic sales language, no manufactured urgency, no
  "I help companies like yours…" boilerplate.
- Do not stack multiple asks. One soft, optional invitation at most.
- This is a DRAFT for human review — do not include placeholders like [Name] or
  [Company]; write it as finished text.

Return ONLY the message text."""


async def generate_message(
    brief: AnalysisResult,
    prospect_name: str,
    *,
    tone: str = "warm",
    length: str = "short",
    goal: str = "start a genuine conversation and build rapport (no hard ask)",
) -> str:
    signals = "; ".join(f"{s.type}: {s.detail}" for s in brief.signals) or "none"
    # Pair each pain with its strongest evidence so openers can be concrete.
    pain_lines = []
    for h in brief.pain_hypotheses:
        ev = f" (evidence: {h.evidence[0]})" if h.evidence else ""
        pain_lines.append(f"{h.hypothesis}{ev}")
    pains = "; ".join(pain_lines) or "none"

    user = (
        f"Prospect: {prospect_name}\n"
        f"Who they are (persona/mindset): {brief.persona_summary or 'n/a'}\n"
        f"Recommended angle: {brief.recommended_angle}\n"
        f"Signals (concrete, verifiable facts to reference): {signals}\n"
        f"Pain hypotheses with evidence (lead with the one that matters most, "
        f"framed as curiosity — never a pitch): {pains}\n\n"
        f"Write a {length}, {tone} first-touch message. Goal: {goal}. "
        f"Remember: earning an honest reply is the only win here — do not push "
        f"for a meeting or call."
    )
    return await router.generate(
        "message_gen",
        [Message("system", _SYSTEM), Message("user", user)],
        options=GenerateOptions(temperature=0.7, max_tokens=512),
    )
